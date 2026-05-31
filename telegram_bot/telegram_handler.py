# pyright: reportOptionalMemberAccess=none, reportOptionalSubscript=none

import logging
import os
import time
import threading
import asyncio
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

from service_log import print_banner
from mqtt_client import MQTTClient, Alert, AlertSeverity
from auth_client import AuthClient, UserRole
from service_state import ServiceStateManager
from data_client import DataClient

logger = logging.getLogger(__name__)

class TelegramBotHandler:
    def __init__(self, token: str, mqtt_client: MQTTClient, auth_client: AuthClient,
                 state_manager: ServiceStateManager, data_client: DataClient):
        self.token = token
        self.mqtt_client = mqtt_client
        self.auth_client = auth_client
        self.state_manager = state_manager
        self.data_client = data_client
        
        self.application = None
        self._loop = None
        self.user_sessions = {}  # telegram_id -> User
        self.alert_subscribers = set()
        self.last_alert_time = {}
        self.alert_cooldown = int(os.environ["ALERT_COOLDOWN"])
        self.valve_ack_timeout = int(os.environ["MQTT_COMMAND_TIMEOUT"])

        self.mqtt_client.add_alert_handler(self._handle_mqtt_alert)
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        username = update.effective_user.username
        
        await update.message.reply_text(
            f"Welcome to IoT Pipeline Monitor Bot!\n\n"
            f"Please authenticate using:\n"
            f"/login <username> <password>\n\n"
            f"Or use /help to see available commands."
        )
        
        logger.info(f"User {username} ({user_id}) started bot")
    # tanin tu in section bayad help command ezafeh koni
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_authenticated_user(update.effective_user.id)
        
        help_text = " **Available Commands:**\n\n"
        help_text += "/start - Initialize bot\n"
        help_text += "/help - Show this help message\n"
        help_text += "/login <username> <password> - Authenticate\n"
        help_text += "/logout - End session\n"
        help_text += "/status [pipeline_id] - System status\n"
        help_text += "/alerts [count] - Recent alerts\n"
        help_text += "/stats [pipeline_id] - Statistics\n"
        help_text += "/subscribe - Subscribe to alerts\n"
        help_text += "/unsubscribe - Unsubscribe from alerts\n"

        if user and user.role in [UserRole.ADMIN, UserRole.OPERATOR]:
            help_text += "\n**Operator Commands:**\n"
            help_text += "/valve <pipeline> <valve> <open/close> - Control valve\n"
            help_text += "/emergency <pipeline> - Emergency shutdown\n"
        
        if user and user.role == UserRole.ADMIN:
            help_text += "\n**Admin Commands:**\n"
            help_text += "/services - Service health status\n"
            help_text += "/thresholds - View thresholds\n"
            help_text += "/users - List users\n"
        
        # TODO(mahdi): Add /report command for daily summaries
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def login_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args or len(context.args) != 2:
            await update.message.reply_text("Usage: /login <username> <password>")
            return
        
        username = context.args[0]
        password = context.args[1]
        telegram_id = str(update.effective_user.id)
        
        user = self.auth_client.register_telegram_user(username, password, telegram_id)
        
        if user:
            self.user_sessions[telegram_id] = user
            self.alert_subscribers.add(telegram_id)
            await update.message.reply_text(
                f"Authentication successful!\n"
                f"Role: {user.role.value}\n"
                f"You are subscribed to alerts. Use /unsubscribe to opt out.\n"
                f"Use /help to see available commands."
            )
            logger.info(f"User {username} authenticated via Telegram and auto-subscribed")
            print_banner(
                "TG USER REGISTERED",
                [
                    f"user:  {username}",
                    f"role:  {user.role.value}",
                    f"tg_id: {telegram_id}",
                ],
                kind="success",
            )
        else:
            await update.message.reply_text("Authentication failed. Check credentials.")
    
    async def logout_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)

        if user_id in self.user_sessions:
            user = self.user_sessions[user_id]
            self.auth_client.logout_user(user.username)
            del self.user_sessions[user_id]
            self.alert_subscribers.discard(user_id)
            await update.message.reply_text("Logged out successfully.")
        else:
            await update.message.reply_text("You are not logged in.")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_authenticated_user(update.effective_user.id)
        if not user:
            await update.message.reply_text("Please /login first.")
            return

        pipeline_id = context.args[0] if context.args else None

        if pipeline_id:
            if not self.auth_client.check_sector_access(user, pipeline_id):
                await update.message.reply_text("Access denied for this pipeline.")
                return

            summary = self._get_live_pipeline_status(pipeline_id)
            if summary:
                status_text = self._format_pipeline_status(summary)
            else:
                status_text = f"Pipeline {pipeline_id} not found."
        else:
            summaries = self._get_live_pipeline_summaries(user)
            status_text = self._format_all_pipelines_status(summaries)

        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_authenticated_user(update.effective_user.id)
        if not user:
            await update.message.reply_text("Please /login first.")
            return
        
        limit = int(context.args[0]) if context.args and context.args[0].isdigit() else 10
        all_alerts = self.state_manager.get_recent_alerts(limit * 3)
        alerts = [
            a for a in all_alerts
            if self.auth_client.check_sector_access(user, a.get('pipeline_id', ''))
        ][:limit]
        
        if not alerts:
            try:
                ts_data = self.data_client.get_anomalies(hours=24)
                if ts_data and 'alerts' in ts_data:
                    alerts = [
                        {
                            'timestamp': a.get('timestamp', 0),
                            'type': a.get('anomaly_type', a.get('alert_type', 'unknown')),
                            'pipeline_id': a.get('pipeline_id', 'unknown'),
                            'severity': a.get('severity', 'info'),
                            'message': a.get('message', ''),
                            'acknowledged': False
                        }
                        for a in ts_data['alerts']
                        if self.auth_client.check_sector_access(user, a.get('pipeline_id', ''))
                    ][:limit]
            except Exception as e:
                logger.error(f"TimeSeries fallback failed: {e}")

        if not alerts:
            await update.message.reply_text("No recent alerts.")
            return

        alert_text = "**Recent Alerts:**\n\n"
        for i, alert in enumerate(alerts, 1):
            timestamp = time.strftime("%H:%M:%S", time.localtime(alert["timestamp"]))
            severity_emoji = self._get_severity_emoji(alert["severity"])
            pipeline_id = alert['pipeline_id'].replace("_", "\\_")
            alert_type = alert['type'].replace("_", "\\_")
            alert_text += (
                f"{i}. {severity_emoji} [{timestamp}] Pipeline {pipeline_id}\n"
                f"   Type: {alert_type}\n"
                f"   {alert['message']}\n\n"
            )
        
        keyboard = [[InlineKeyboardButton("Acknowledge All", callback_data="ack_all_alerts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await update.message.reply_text(alert_text, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception:
            await update.message.reply_text(alert_text.replace("**", "").replace("\\_", "_"), reply_markup=reply_markup)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_authenticated_user(update.effective_user.id)
        if not user:
            await update.message.reply_text("Please /login first.")
            return

        if not context.args:
            all_pipelines = self.data_client.get_all_pipelines()
            accessible = [p for p in all_pipelines if self.auth_client.check_sector_access(user, p)]
            if accessible:
                pipeline_list = ', '.join(accessible)
                await update.message.reply_text(
                    f"Usage: /stats <pipeline_id>\n\n"
                    f"Available pipelines: {pipeline_list}"
                )
            else:
                await update.message.reply_text("No pipelines available for your sector.")
            return

        pipeline_id = context.args[0]

        if not self.auth_client.check_sector_access(user, pipeline_id):
            await update.message.reply_text("Access denied for this pipeline.")
            return

        pipeline_config = self.data_client.get_pipeline_config(pipeline_id)
        if not pipeline_config or "bolts" not in pipeline_config:
            await update.message.reply_text(f"Pipeline {pipeline_id} not found.")
            return

        bolts = pipeline_config.get("bolts", [])
        if not bolts:
            await update.message.reply_text(f"No sensors found for pipeline {pipeline_id}.")
            return

        all_temp_stats = []
        all_pressure_stats = []
        for bolt in bolts:
            bid = bolt["id"]
            t = self.data_client.get_statistics(pipeline_id, bolt_id=bid, sensor="temperature")
            p = self.data_client.get_statistics(pipeline_id, bolt_id=bid, sensor="pressure")
            if t and isinstance(t, dict):
                all_temp_stats.append(t.get("statistics", t))
            if p and isinstance(p, dict):
                all_pressure_stats.append(p.get("statistics", p))

        def aggregate_stats(stats_list):
            valid = [s for s in stats_list if s and s.get("count", 0) > 0]
            if not valid:
                return None
            return {
                "mean": round(sum(s.get("mean", 0) for s in valid) / len(valid), 2),
                "std_dev": round(sum(s.get("std_dev", 0) for s in valid) / len(valid), 2),
                "min": min(s.get("min", 0) for s in valid),
                "max": max(s.get("max", 0) for s in valid),
                "count": sum(s.get("count", 0) for s in valid),
            }

        temp_stats = aggregate_stats(all_temp_stats)
        pressure_stats = aggregate_stats(all_pressure_stats)
        anomalies = self.data_client.get_anomalies(pipeline_id, hours=24)

        bolt_label = f" ({len(bolts)} bolts)" if len(bolts) > 1 else ""
        stats_text = f"**Pipeline {pipeline_id} Statistics (24h){bolt_label}:**\n\n"

        if temp_stats and temp_stats.get("count", 0) > 0:
            stats_text += "**Temperature:**\n"
            stats_text += self.data_client.format_statistics(temp_stats) + "\n\n"
        else:
            stats_text += "**Temperature:** No data available\n\n"

        if pressure_stats and pressure_stats.get("count", 0) > 0:
            stats_text += "**Pressure:**\n"
            stats_text += self.data_client.format_statistics(pressure_stats) + "\n\n"
        else:
            stats_text += "**Pressure:** No data available\n\n"

        if anomalies:
            stats_text += "**Recent Anomalies:**\n"
            stats_text += self.data_client.format_anomalies(anomalies).replace("_", "\\_")
        else:
            stats_text += "**Recent Anomalies:** None detected"

        try:
            await update.message.reply_text(stats_text, parse_mode='Markdown')
        except Exception:
            await update.message.reply_text(stats_text.replace("**", "").replace("\\_", "_"))
    
    async def valve_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_authenticated_user(update.effective_user.id)
        if not user:
            await update.message.reply_text("Please /login first.")
            return
        
        if not self.auth_client.check_permission(user, "valve_control"):
            await update.message.reply_text("Insufficient permissions.")
            return
        
        if not context.args or len(context.args) != 3:
            await update.message.reply_text(
                "Usage: /valve <pipeline_id> <valve_id> <open/close>\n"
                "Example: /valve N1 valve_n1 close"
            )
            return
        
        pipeline_id = context.args[0]
        valve_id = context.args[1]
        action = context.args[2].lower()
        
        if action not in ["open", "close"]:
            await update.message.reply_text("Action must be 'open' or 'close'.")
            return
        
        if not self.auth_client.check_sector_access(user, pipeline_id):
            await update.message.reply_text("Access denied for this pipeline.")
            return
        
        success = self.mqtt_client.send_valve_command(
            pipeline_id, valve_id, action, user.username
        )
        
        if success:
            self.state_manager.add_command({
                "pipeline_id": pipeline_id,
                "valve_id": valve_id,
                "command": action,
                "user_id": user.username
            })

            await update.message.reply_text(
                f"Command sent: {action} valve {valve_id} on pipeline {pipeline_id}\n"
                f"Waiting for confirmation..."
            )
            logger.info(f"Valve command from {user.username}: {action} {valve_id}")

            chat_id = update.effective_chat.id
            loop = self._loop
            assert loop is not None

            def on_valve_ack(ack_pipeline, ack_valve, ack_success):
                if ack_success is None:
                    msg = f"Valve command timed out for {valve_id} on {pipeline_id}. The command may still execute."
                elif ack_success:
                    msg = f"Confirmed: valve {valve_id} on pipeline {pipeline_id} is now {action}."
                else:
                    msg = f"Valve command failed for {valve_id} on pipeline {pipeline_id}."
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.application.bot.send_message(chat_id=chat_id, text=msg),
                        loop
                    )
                except Exception as e:
                    logger.error(f"Failed to send valve ack to user: {e}")

            self.mqtt_client.register_pending_command(pipeline_id, valve_id, on_valve_ack, timeout=self.valve_ack_timeout)
        else:
            await update.message.reply_text("Failed to send command.")
    
    async def emergency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_authenticated_user(update.effective_user.id)
        if not user:
            await update.message.reply_text("Please /login first.")
            return
        
        if not self.auth_client.check_permission(user, "emergency_shutdown"):
            await update.message.reply_text("Insufficient permissions.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /emergency <pipeline_id>")
            return
        
        pipeline_id = context.args[0]
        
        if not self.auth_client.check_sector_access(user, pipeline_id):
            await update.message.reply_text("Access denied for this pipeline.")
            return
        
        keyboard = [[
            InlineKeyboardButton("CONFIRM SHUTDOWN", callback_data=f"emergency_{pipeline_id}"),
            InlineKeyboardButton("Cancel", callback_data="cancel")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"**EMERGENCY SHUTDOWN**\n\n"
            f"This will close ALL valves on pipeline {pipeline_id}.\n"
            f"Are you sure?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    # -- Tanin add subscription feature --
    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_authenticated_user(update.effective_user.id)
        if not user:
            await update.message.reply_text("Please /login first.")
            return

        user_id = str(update.effective_user.id)
        self.alert_subscribers.add(user_id)

        await update.message.reply_text(
            "Subscribed to alerts.\n"
            "You will receive notifications for critical events.\n"
            "Use /unsubscribe to stop."
        )
        logger.info(f"User {user.username} subscribed to alerts")

    async def unsubscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_authenticated_user(update.effective_user.id)
        if not user:
            await update.message.reply_text("Please /login first.")
            return

        user_id = str(update.effective_user.id)

        if user_id in self.alert_subscribers:
            self.alert_subscribers.remove(user_id)
            await update.message.reply_text("Unsubscribed from alerts.")
        else:
            await update.message.reply_text("You were not subscribed.")
    
    async def services_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_authenticated_user(update.effective_user.id)
        if not user or user.role != UserRole.ADMIN:
            await update.message.reply_text("Admin access required.")
            return

        health_response = self.data_client.get_service_health()

        status_text = "Service Health:\n\n"

        if health_response and isinstance(health_response, dict):
            services = health_response.get("health_status", health_response)
            if not services:
                status_text += "No services registered."
            else:
                for service_key, info in services.items():
                    if isinstance(info, dict):
                        is_online = info.get("status") == "healthy"
                        status_indicator = "[OK]" if is_online else "[DOWN]"
                        service_name = info.get("name", service_key)
                        status = info.get("status", "unknown")
                        status_text += f"{status_indicator} {service_name}: {status}\n"
                    else:
                        status_text += f"[?] {service_key}: {info}\n"
        else:
            status_text += "Unable to fetch service health from Catalog."

        await update.message.reply_text(status_text)
    
    async def thresholds_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_authenticated_user(update.effective_user.id)
        if not user or user.role != UserRole.ADMIN:
            await update.message.reply_text("Admin access required.")
            return
        
        thresholds = self.data_client.get_thresholds()
        
        if not thresholds:
            await update.message.reply_text("Unable to retrieve thresholds.")
            return
        
        threshold_data = thresholds.get("thresholds", {})
        
        text = "**System Thresholds:**\n\n"
        
        temp_thresholds = threshold_data.get("temperature", {})
        if temp_thresholds:
            text += "**Temperature:**\n"
            text += f"  Normal: {temp_thresholds.get('min_normal', 0)}-{temp_thresholds.get('max_normal', 0)}°C\n"
            text += f"  Alert: >{temp_thresholds.get('alert', 0)}°C\n"
            text += f"  Critical: >{temp_thresholds.get('critical', 0)}°C\n\n"
        
        pressure_thresholds = threshold_data.get("pressure", {})
        if pressure_thresholds:
            text += "**Pressure:**\n"
            text += f"  Normal: {pressure_thresholds.get('min_normal', 0)}-{pressure_thresholds.get('max_normal', 0)} PSI\n"
            text += f"  Alert: >{pressure_thresholds.get('alert', 0)} PSI\n"
            text += f"  Critical: >{pressure_thresholds.get('critical', 0)} PSI\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._get_authenticated_user(update.effective_user.id)
        if not user or user.role != UserRole.ADMIN:
            await update.message.reply_text("Admin access required.")
            return
        
        active_sessions = len(self.user_sessions)
        subscribers = len(self.alert_subscribers)
        
        text = "**User Management:**\n\n"
        text += f"Active Sessions: {active_sessions}\n"
        text += f"Alert Subscribers: {subscribers}\n\n"
        
        if self.user_sessions:
            text += "**Active Telegram Sessions:**\n"
            for telegram_id, session_user in self.user_sessions.items():
                text += f"• {session_user.username} ({session_user.role.value})\n"

        catalog_users = self.data_client.get_catalog_users()
        if catalog_users:
            text += "\n**System Users:**\n"
            for cat_user in catalog_users:
                username = cat_user.get('userName', 'unknown')
                chat_id = cat_user.get('chatID')
                sectors = cat_user.get('sectors', [])
                sector_names = ', '.join(
                    s.get('sectorID', s) if isinstance(s, dict) else str(s)
                    for s in sectors
                ) if sectors else 'none'
                chat_info = f" [chat:{chat_id}]" if chat_id else ""
                text += f"• {username}{chat_info} - Sectors: {sector_names}\n"

        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "ack_all_alerts":
            count = len(self.state_manager.alerts_history)
            for i in range(count):
                self.state_manager.acknowledge_alert(i)
            await query.edit_message_text("All alerts acknowledged.")
            
        elif data.startswith("emergency_"):
            pipeline_id = data.split("_")[1]
            user = self._get_authenticated_user(query.from_user.id)

            if user:
                pipeline_config = self.data_client.get_pipeline_config(pipeline_id)
                if pipeline_config and "valves" in pipeline_config:
                    valve_ids = [v["id"] for v in pipeline_config["valves"]]
                    for valve_id in valve_ids:
                        self.mqtt_client.send_valve_command(
                            pipeline_id, valve_id, "close", user.username
                        )
                else:
                    logger.warning(f"No valves found for pipeline {pipeline_id}")
                    valve_ids = []
                
                await query.edit_message_text(
                    f"EMERGENCY SHUTDOWN EXECUTED\n"
                    f"All valves on pipeline {pipeline_id} closed."
                )
                logger.warning(f"Emergency shutdown by {user.username} for pipeline {pipeline_id}")
                
        elif data == "cancel":
            await query.edit_message_text("Operation cancelled.")
    
    def _handle_mqtt_alert(self, alert: Alert):
        logger.info(f"MQTT Alert received: {alert.pipeline_id} - {alert.alert_type} - {alert.severity.value}")
        if alert.severity in [AlertSeverity.WARNING, AlertSeverity.ALERT, AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
            logger.info(f"Broadcasting alert (severity: {alert.severity.value})")
            self._broadcast_alert(alert)
        else:
            logger.info(f"Alert not broadcast (severity {alert.severity.value} too low)")
        
        self.state_manager.add_alert({
            "alert_type": alert.alert_type,
            "pipeline_id": alert.pipeline_id,
            "message": alert.message,
            "severity": alert.severity.value,
            "timestamp": alert.timestamp
        })
    
    def _broadcast_alert(self, alert: Alert):
        # Old broadcast implementation - was too slow with many subscribers
        # for subscriber_id in self.alert_subscribers:
        #     await self.application.bot.send_message(subscriber_id, message)
        # Now using run_coroutine_threadsafe for better performance

        alert_key = f"{alert.pipeline_id}_{alert.alert_type}"
        current_time = time.time()

        if alert_key in self.last_alert_time:
            if current_time - self.last_alert_time[alert_key] < self.alert_cooldown:
                return  # still in cooldown

        self.last_alert_time[alert_key] = current_time
        
        severity_emoji = self._get_severity_emoji(alert.severity.value)
        safe_pipeline = alert.pipeline_id.replace("_", "\\_")
        safe_type = alert.alert_type.replace("_", "\\_")
        safe_message = alert.message.replace("_", "\\_")
        message = (
            f"{severity_emoji} *ALERT*\n\n"
            f"Pipeline: {safe_pipeline}\n"
            f"Type: {safe_type}\n"
            f"Severity: {alert.severity.value.upper()}\n"
            f"Message: {safe_message}"
        )
        
        if not self._loop or not self.application:
            logger.warning("Cannot broadcast alert: bot not fully initialized")
            return

        targeted_chat_ids = alert.data.get("recipient_chat_ids") if alert.data else None
        subscribed_ids = {str(s) for s in self.alert_subscribers}

        if targeted_chat_ids is not None:
            targeted_str = {str(c) for c in targeted_chat_ids}
            recipients = list(targeted_str & subscribed_ids)
            logger.info(f"Analytics eligible: {len(targeted_str)}, subscribed: {len(subscribed_ids)}, sending to: {len(recipients)}")
        else:
            recipients = list(subscribed_ids)
            logger.info(f"Broadcasting to {len(recipients)} subscribers (fallback mode)")

        sev = alert.severity.value
        alert_kind = "danger" if sev in ("critical", "emergency", "alert") else ("warning" if sev == "warning" else "info")
        print_banner(
            "TG ALERT",
            [
                f"pipe:  {alert.pipeline_id}",
                f"type:  {alert.alert_type}",
                f"sev:   {sev}",
                f"to:    {len(recipients)} subscribers",
            ],
            kind=alert_kind,
        )

        for subscriber_id in recipients:
            user = self.user_sessions.get(subscriber_id)
            if user and not self.auth_client.check_sector_access(user, alert.pipeline_id):
                logger.info(f"Skipping alert for {subscriber_id} - no access to pipeline {alert.pipeline_id}")
                continue

            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.application.bot.send_message(
                        chat_id=subscriber_id,
                        text=message,
                        parse_mode='Markdown'
                    ),
                    self._loop
                )
                future.add_done_callback(
                    lambda f, sid=subscriber_id: logger.error(f"Alert send failed for {sid}: {f.exception()}") if f.exception() else None
                )
                logger.info(f"Alert scheduled for {subscriber_id}")
            except Exception as e:
                logger.error(f"Failed to send alert to {subscriber_id}: {e}")
    
    def _get_authenticated_user(self, telegram_user_id):
        user_id = str(telegram_user_id)
        return self.user_sessions.get(user_id)
    
    def _get_severity_emoji(self, severity: str) -> str:
        
        labels = {
            "info": "[INFO]",
            "warning": "[WARN]",
            "alert": "[ALERT]",
            "critical": "[CRITICAL]",
            "emergency": "[EMERGENCY]"
        }
        return labels.get(severity, "[?]")
    
    def _get_live_pipeline_summaries(self, user=None) -> Dict:
        try:
            summaries = {}
            for pid in self.data_client.get_all_pipelines():
                if user and not self.auth_client.check_sector_access(user, pid):
                    continue
                summary = self.data_client.get_pipeline_live_summary(pid)
                if summary:
                    summaries[pid] = summary
            return summaries
        except Exception as e:
            logger.error(f"Error fetching live pipeline data in Telegram handler: {e}")
            return self.state_manager.get_pipeline_summary() or {}

    def _get_live_pipeline_status(self, pipeline_id: str) -> Optional[Dict]:
        try:
            return self.data_client.get_pipeline_live_summary(pipeline_id)
        except Exception as e:
            logger.error(f"Error fetching live status for pipeline {pipeline_id}: {e}")
            return None
    
    def _format_pipeline_status(self, summary: Dict) -> str:
        pipeline_id = summary['pipeline_id'].replace("_", "\\_")

        text = f"**Pipeline {pipeline_id} Status**\n\n"
        text += f"Status: {summary['status'].upper()}\n"
        text += f"Temperature: {summary['temperature_avg']}°C\n"
        text += f"Pressure: {summary['pressure_avg']} PSI\n"
        text += f"Bolts: {summary['bolt_count']}\n"
        text += f"Anomalies: {summary['anomaly_count']}\n"
        text += f"Health: {summary['health_score']}%\n\n"

        text += "**Valves:**\n"
        for valve_id, state in summary["valve_states"].items():
            escaped_valve_id = valve_id.replace("_", "\\_")
            text += f"  - {escaped_valve_id}: {state}\n"

        return text
    
    def _format_all_pipelines_status(self, summaries: Dict) -> str:
        text = "**System Overview**\n\n"

        for pipeline_id, summary in summaries.items():
            text += f"**Pipeline {pipeline_id}** [{summary['status'].upper()}]\n"
            text += f"  Temp: {summary['temperature_avg']}°C | "
            text += f"Pressure: {summary['pressure_avg']} PSI\n"
            text += f"  Anomalies: {summary['anomaly_count']} | "
            text += f"Health: {summary['health_score']}%\n\n"

        return text
    
    async def edited_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.edited_message.reply_text(
            "Edited commands are not processed. Please send a new command."
        )
    
    async def run(self):
        self.application = Application.builder().token(self.token).build()
        
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("login", self.login_command))
        self.application.add_handler(CommandHandler("logout", self.logout_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("alerts", self.alerts_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("valve", self.valve_command))

        self.application.add_handler(CommandHandler("emergency", self.emergency_command))
        self.application.add_handler(CommandHandler("subscribe", self.subscribe_command))
        self.application.add_handler(CommandHandler("unsubscribe", self.unsubscribe_command))
        self.application.add_handler(CommandHandler("services", self.services_command))

        self.application.add_handler(CommandHandler("thresholds", self.thresholds_command))
        self.application.add_handler(CommandHandler("users", self.users_command))
        self.application.add_handler(CallbackQueryHandler(self.callback_handler))
        self.application.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & filters.COMMAND, self.edited_message_handler))
        
        logger.info("Starting Telegram bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        self._loop = asyncio.get_running_loop()
        logger.info(f"Event loop stored for async messaging")

        try:
            while True:
                await asyncio.sleep(1)
                self.mqtt_client.check_command_timeouts()
        except asyncio.CancelledError:
            logger.info("Telegram bot stopped")
            raise
    
    def stop(self):
        if self.application and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(self.application.stop(), self._loop)
            except Exception as e:
                logger.error(f"Error stopping Telegram bot: {e}")
            logger.info("Telegram bot stopped")