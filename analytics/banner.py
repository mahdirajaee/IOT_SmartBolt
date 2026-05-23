SENSOR_UNIT = {'temperature': 'C', 'pressure': 'PSI'}

RED    = "\033[91m"
ORANGE = "\033[33m"
RESET  = "\033[0m"

def print_alert(severity, pipeline_id, sensor, value, threshold):
    unit = SENSOR_UNIT.get(sensor, '')
    try:
        v = f"{float(value):.2f}{unit}"
        t = f"{float(threshold):.0f}{unit}"
    except (TypeError, ValueError):
        v, t = f"{value}{unit}", f"{threshold}{unit}"

    color = RED if severity.lower() == "critical" else ORANGE if severity.lower() == "warning" else ""
    print(f"{color}>>> {severity.upper()} {pipeline_id} {sensor}={v} over {t}{RESET}", flush=True)


def print_banner(title, lines=None, kind='info'):
    header = f"*** {title.upper()} ***"
    print(f"\n{header}", flush=True)
    for ln in lines or []:
        print(f"  {ln}", flush=True)
