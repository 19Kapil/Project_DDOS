import subprocess

subprocess.Popen(["gnome-terminal", "--title=Controller 1","--", "bash", "-c", 
    "cd Mitigation && ryu-manager mitigation.py --observe-links --ofp-tcp-listen-port 6653 --wsapi-port 8055; exec bash, shell=True"])

subprocess.Popen(["gnome-terminal", "--title=Controller 2","--", "bash", "-c", 
    "cd Mitigation && ryu-manager mitigation2.py --observe-links --ofp-tcp-listen-port 6654 --wsapi-port 8055; exec bash"])

subprocess.Popen(["gnome-terminal", "--title=Controller 3","--", "bash", "-c", 
    "cd Mitigation && ryu-manager mitigation3.py --observe-links --ofp-tcp-listen-port 6655 --wsapi-port 8055; exec bash"])


subprocess.Popen(["gnome-terminal", "--title=Load Balance","--", "bash", "-c", 
    "cd Controller && sudo python3 main.py; exec bash"])

