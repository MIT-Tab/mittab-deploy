import paramiko
from scp import SCPClient


def exec_commands(host, *commands):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()
    client.connect(host, username='root')

    for command in commands:
        channel = client.get_transport().open_session()
        channel.exec_command(command)
        exit_code = channel.recv_exit_status()
        if exit_code != 0:
            raise ValueError("'%s' returned exit code %s" % (command, exit_code))


def get_file(host, src, dst):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.load_system_host_keys()
    ssh_client.connect(host, username='root')

    scp_client = SCPClient(ssh_client.get_transport())
    scp_client.get(src, dst, recursive=True)
