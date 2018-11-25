import subprocess


def setup_var_protection(env):
    global cmd_rw, cmd_ro
    cmd_rw = env['cmd_var_rw']
    cmd_ro = env['cmd_var_ro']


def unlock():
    subprocess.call(cmd_rw)


def lock():
    subprocess.call(cmd_ro)
