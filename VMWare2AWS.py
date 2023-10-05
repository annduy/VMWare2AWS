import subprocess
import os
import json
import threading
import time
import sys
from datetime import datetime

aws_cli = 'C:\\Program Files\\Amazon\\AWSCLIV2\\aws.exe'
ovf_tool = 'C:\\Program Files\\VMware\\VMware OVF Tool\\ovftool.exe'
powershell = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"

###### VMWare VM info
vmdk_path ='G:\\VMWare-VMs\\UbuntuServer20046'
vmx_file = 'UbuntuServer20046.vmx'

###### AWS info
aws_bucket = "annduybucket"


def current_date_time_string():
    current_datetime = datetime.now()
    current_datetime_string = current_datetime.strftime("%d/%m/%Y - %H:%M:%S")
    return current_datetime_string

def obtain_vm_name(vmdk_path):
    tokens = vmdk_path.split('\\')
    vm_name = tokens[-1] + '-vm'
    return vm_name

def generate_ova_filename(vm_name):
    ova_filename = vm_name.replace('-vm','.ova')
    return ova_filename

def powershell_in_subprocess(command, queue):
    result = subprocess.run([powershell,'-command',command],stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    queue.put(result)

def run_ps_command_in_thread(command):
    global result_queue
    task = threading.Thread(target = lambda: powershell_in_subprocess(command,result_queue))
    task.start()
    task_progress(task)
    result = result_queue.get()
    if result.stdout != '':
        print("Result out from thread: ", result.stdout)
    if result.stderr != '':
        print("Warning(s)/Error(s) from thread: ", result.stderr)  

def task_progress(task):
    while task.is_alive():
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(0.5)
    # Print a final newline character to ensure the last line is wrapped
    print()    

vm_name = obtain_vm_name(vmdk_path) 
ova_file_name = generate_ova_filename(vm_name)
#### remove the existing OVA file
if os.path.exists(f'{vmdk_path}\{vmx_file}'):
    subprocess.run( f'del {vmdk_path}\{ova_file_name}', shell=True, check=True)

#### Convert VMWare VM to OVA file     
print(current_date_time_string() + ' : ' + "Convert a VMware VM to OVA file")
subprocess.run( [f'{ovf_tool}', f'{vmdk_path}\{vmx_file}', f'{vmdk_path}\{ova_file_name}'], shell=True, check=True)
print(current_date_time_string() + ' : ' + "OVA file was created")
print("--------------------------------------------")


#### Upload the OVA file to AWS
print(current_date_time_string() + ' : ' + "Upload OVA file to AWS")
subprocess.run( f'aws s3 cp {vmdk_path}\\{ova_file_name} s3://{aws_bucket}/{ova_file_name}', shell=True, check=True) 
print(current_date_time_string() + ' : ' + "OVA file was uploaded to AWS")
print("--------------------------------------------")


#### Create AWS image
print(current_date_time_string() + ' : ' + "Create AWS image from OVA file")
creat_vm_cmd = f'aws ec2 import-image --disk-containers Format=ova,UserBucket="{{S3Bucket={aws_bucket},S3Key={ova_file_name}}}" --query "ImportTaskId" --output json'
result = subprocess.run( creat_vm_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=True) 
print(current_date_time_string() + ' : ' + "Creation job was submitted")
output_json = json.loads(result.stdout)
import_task_id = output_json.strip()

print(current_date_time_string() + ' : ' + "Checking creation job in background")
task_monitor_cmd = f'aws ec2 describe-import-image-tasks --import-task-ids {import_task_id} --query "ImportImageTasks[0].[Status, ImageId]" --output json'
image_id = ''
while True:
    sys.stdout.write(".")
    sys.stdout.flush()
    result = subprocess.run( task_monitor_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=True)
    output_json = json.loads(result.stdout)
    task_status = output_json[0]
    image_id = output_json[1]
    if task_status ==  'completed':
        break
    time.sleep(0.5)
print('')
print(current_date_time_string() + ' : ' + "Creation job is completed")
print("--------------------------------------------")

#### Start AWS instance from AWS image 
print(current_date_time_string() + ' : ' + "Start the AWS Instance")
tag_specification = f"ResourceType=instance,Tags=[{{Key=Name,Value={vm_name}}}]"
vm_start_cmd = f'aws ec2 run-instances --image-id {image_id} --instance-type "t2.micro" --tag-specifications "{tag_specification}"'
subprocess.run( vm_start_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=True) 
print(current_date_time_string() + ' : ' + "AWS VM was started")

print("Housekeeping now:")

#### Delete OVA file on AWS
print(current_date_time_string() + ' : ' + "Delete OVA file on AWS")
subprocess.run( f'aws s3 rm s3://{aws_bucket}/{ova_file_name}', shell=True, check=True) 
print(current_date_time_string() + ' : ' + "OVA file on AWS was deleted")
print("--------------------------------------------")

#### Delete local OVA
print(current_date_time_string() + ' : ' + "Delete local OVA file")
subprocess.run( f'del {vmdk_path}\{ova_file_name}', shell=True, check=True) 
print(current_date_time_string() + ' : ' + "Local OVA file was deleted")
print("--------------------------------------------")

print("Your VM is on AWS now. Enjoy with AWS!!!")