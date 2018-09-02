import os.path
import importlib.util

from ec2mc import consts

# TODO: Offer JSON validation for handler JSON files.
def main(instance, new_ip):
    """pass along instance info to handler under config's ip_handlers"""
    if consts.USE_HANDLER is False:
        return
    if 'IpHandler' not in instance['tags']:
        return
    handler_script = instance['tags']['IpHandler']

    handler_path = f"{consts.IP_HANDLER_DIR}{handler_script}"
    if not os.path.isfile(handler_path):
        print(f"  {handler_script} not found from config's ip_handlers.")
        return

    handler = load_script(handler_path)
    if handler is not None:
        handler.main(
            instance['region'], instance['name'], instance['id'], new_ip)


def load_script(script_path):
    """load python script"""
    try:
        spec = importlib.util.spec_from_file_location("handler", script_path)
        handler = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(handler)
        return handler
    except ImportError as e:
        handler_base = os.path.basename(script_path)
        print(f"  {e.name} package required by {handler_base} not found.")
        print(f"    Install with \"pip install {e.name}\".")
    return None