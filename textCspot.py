import psutil

for proc in psutil.process_iter(attrs=['pid', 'name', 'username']):
    print(proc.info['name'])
