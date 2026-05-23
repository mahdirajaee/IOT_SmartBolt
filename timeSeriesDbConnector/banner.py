def print_event(label, message, color='cyan'):
    print(f">>> {label} {message}", flush=True)


def print_banner(title, lines=None, kind='info'):
    header = f"*** {title.upper()} ***"
    print(f"\n{header}", flush=True)
    for ln in lines or []:
        print(f"  {ln}", flush=True)
