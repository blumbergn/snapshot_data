import json
import pprint
import os,sys
import boto3
from collections import Counter,defaultdict
import datetime
import time

# #################################################################################
#  For each snapshot group:
## total number of snapshots
## total size of snapshots
## Get oldest snapshot date
## get newest snapshot date
## check if instance-id exists and what state it's in
## get AMI information
# #################################################################################

# Global vars
cur_dir = os.path.dirname(sys.argv[0])
data_dir = os.path.join(cur_dir,'snapshot/data/')
snap_shot_dir = os.path.join(cur_dir,'snapshot/')
os.environ["AWS_SHARED_CREDENTIALS_FILE"]="{PATH_TO_SHARED_CREDENTIALS_FILE}"
pp = pprint.PrettyPrinter()
regions = ['us-east-1','us-east-2','us-west-1','us-west-2']
OwnerIds = ['{ACCOUNT_ID_TO_RUN_AGAINST}']
profile = '{PROFILE_TO_RUN_AGAINST}'




def get_client(resource,region):
    client = boto3.Session(profile_name=profile,region_name=region).client(resource)
    
    
    return client

def get_total_snap_size(region):
    total_gb = 0
    ec2_cli = get_client('ec2',region)
    snap_shots = ec2_cli.describe_snapshots(OwnerIds=OwnerIds)

    total_snaps = len(snap_shots['Snapshots'])

    for snap in snap_shots['Snapshots']:
        
        total_gb = total_gb + snap['VolumeSize']
 
    return total_snaps, total_gb

def get_total_volumes(region):
    
    available_volume_size = 0
    available_volumes = 0
    ec2_cli = get_client('ec2',region)
    volumes = ec2_cli.describe_volumes()

    for volume in volumes['Volumes']:
        if volume['State'] == 'available':
            available_volumes += 1
            available_volume_size = available_volume_size + volume['Size']


    return available_volumes, available_volume_size

def get_snapshot_servers(region):


    ec2_cli = get_client('ec2',region)
    snap_shots = ec2_cli.describe_snapshots(MaxResults=10,OwnerIds=OwnerIds)
    for snap_shot in snap_shots['Snapshots']:
        if 'Created by CreateImage' in snap_shot['Description']:
            snap_shot_desc = snap_shot['Description']
            server_source = snap_shot_desc.split()
            server_source = str(server_source[2])
            server_source = server_source.split("(")
            server_source = str(server_source[1])
            server_source = server_source.replace(")","")
            print(server_source)
            try:
                instance = ec2_cli.describe_instances(InstanceIds=[server_source])
                pp.pprint(instance['Reservations'])
            
            except Exception as e:
                print(e)
    

    return 



def instances_by_type(region):
    
    instance_types = []
    
    ec2_cli = get_client('ec2',region)
    instances = ec2_cli.describe_instances(Filters=[{'Name': 'instance-state-name','Values':['running']}])
    for instance in instances['Reservations']:
        for inst in instance['Instances']:
            
            instance_types.append(inst["InstanceType"])
            

            
    instance_type_count = {}
    for item in instance_types:
        if item in instance_type_count:
            instance_type_count[item] = instance_type_count.get(item)+1
        else:
            instance_type_count[item] = 1
    
 

     
    return instance_type_count

def instance_details_by_type(region,instance_type):
    inst_records = defaultdict(list)
    ec2_cli = get_client('ec2',region)
    instances = ec2_cli.describe_instances(Filters=[{'Name': 'instance-state-name','Values':['running'],'Name': 'instance-type','Values':[instance_type]}])
    instance = instances['Reservations']
    
    for inst in instance:
        for ins in inst['Instances']:
            instance_id = ins['InstanceId']
            try:
                tags_list = ins['Tags']
                for tag in tags_list:
                    if tag['Key'] == 'Name':
                        instance_name = tag['Value']
            except Exception as e:
                print(str(e))
            if ins['State']['Name'] == 'running':
                try:
                    launch_time = str((ins['LaunchTime'])) 
                    launch_time = launch_time.split(' ')
                    launch_time = launch_time[0]
                    inst_records[instance_id].append({'InstanceType': ins['InstanceType']})
                    inst_records[instance_id].append({'Name': instance_name})
                    inst_records[instance_id].append({'LaunchTime': launch_time})
                    inst_records[instance_id].append({'AZ': ins['Placement']['AvailabilityZone']})
                    inst_records[instance_id].append({'PrivateIP': ins['PrivateIpAddress']})
                    inst_records[instance_id].append({'State': ins['State']['Name']})
                except Exception as e:
                    print("Failed on instance: " + instance_id + "Because of: " + str(e))
                
        
        

    return inst_records

def get_instance_by_id(instance_id,region):
    ec2_cli = get_client('ec2',region)  
    instance_name = "NO LONGER EXISTS"
    instance_state = ''
    instance_launch_date = ''


    try:
        instance_details = ec2_cli.describe_instances(InstanceIds=[instance_id])
    except Exception as e:
        print(str(e))
    
    # get instance name
    try:
        for tag in instance_details['Reservations'][0]['Instances'][0]['Tags']:
            if tag['Key'] == 'Name':
                instance_name = tag['Value']
                for char in  ':}':
                    instance_name = instance_name.replace(char,'')
    
    except Exception as e:
        print(str(e))

    # get instance state
    try:
        instance_state = instance_details['Reservations'][0]['Instances'][0]['State']['Name']
    
    except Exception as e:
        print(str(e))
    
    # get launch time
    try:
        instance_launch_date = instance_details['Reservations'][0]['Instances'][0]['LaunchTime'].strftime('%Y-%m-%d')
    
    except Exception as e:
        print(str(e))


    return instance_name,instance_state,instance_launch_date

def output_snapshot_data(total_snaps,total_size,snap_info,out_file,region,total_cost_month):

    with open(out_file, 'a') as f:
        
        f.write("Total Snapshots : %s \n\n\n" % (total_snaps))  
        f.write("InstanceID : Instance Name : Instance State : Instance Launch Date : Earliest Snapshot : Latest Snapshot : Snapshot Sizes GB : Number of Snapshots\n")

        for instance in snap_info:
            earliest_snap = snap_info[instance]['Earliest Snap']
            latest_snap = snap_info[instance]['Latest Snap']
            total_snap_size = snap_info[instance]['Snapshot Sizes']
            total_instance_snaps = snap_info[instance]['Total Snaps']

            instance_name,instance_state,instance_launch_date = get_instance_by_id(instance,region)

            f.write(" %s :  %s : %s : %s : %s : %s : %s : %s \n" % (instance,instance_name,instance_state,instance_launch_date,earliest_snap,latest_snap,total_snap_size,total_instance_snaps) )
    
    return

def get_snap_shots(region):
    ec2_cli = get_client('ec2',region)
    snap_shots = ec2_cli.describe_snapshots(OwnerIds=OwnerIds)


    return snap_shots['Snapshots']

def get_snaps_by_description(snap_type,snaps):
    total_count = 0
    snap_info = {}
    server_source = ''
    size_by_instance = 0
    total_cost_month = 0
    combined_snap_size = 0
    
    total_size = 0

    for snap in snaps:
        description = str(snap['Description'])

        if snap_type in description:
            total_count += 1

            # Get the instance-id associated with the snapshot
            server_source = description.split()
            server_source = str(server_source[2])
            server_source = server_source.split("(")
            server_source = str(server_source[1])
            server_source = str(server_source.replace(")",""))

            snap_info.setdefault(server_source, {}) ['Snapshot Sizes']= []
            snap_info.setdefault(server_source, {}) ['Earliest Snap'] = ''
            snap_info.setdefault(server_source, {}) ['Latest Snap'] = ''
            snap_info.setdefault(server_source, {}) ['Total Snaps'] = 0   
            snap_info.setdefault(server_source, {}) ['start dates'] = []

    for snap in snaps:
        snap_size = snap['VolumeSize']
        
        description = str(snap['Description'])
        snap_date = snap['StartTime'].strftime('%Y-%m-%d')
        if snap_type in description:
            total_size = total_size + snap_size
            
            # Get the instance-id associated with the snapshot
            server_source = description.split()
            server_source = str(server_source[2])
            server_source = server_source.split("(")
            server_source = str(server_source[1])
            server_source = str(server_source.replace(")",""))
            
            if snap_size not in snap_info[server_source]['Snapshot Sizes']:
                snap_info[server_source]['Snapshot Sizes'].append(snap_size)
                combined_snap_size = combined_snap_size + snap_size



            snap_info[server_source]['Total Snaps'] = snap_info[server_source]['Total Snaps'] + 1
            snap_info[server_source]['start dates'].append(snap_date)
            snap_info[server_source]['start dates'].sort(key=lambda x: time.mktime(time.strptime(x,"%Y-%m-%d")))
            snap_info[server_source]['Earliest Snap'] = snap_info[server_source]['start dates'][0]
            last_element = len(snap_info[server_source]['start dates']) - 1
            snap_info[server_source]['Latest Snap'] = snap_info[server_source]['start dates'][last_element]
                   
    print ('Total size in snapshots is : ' + str(combined_snap_size))
    total_cost_month = total_size * .05
    return total_count, total_size, snap_info, total_cost_month

def main():


    if not os.path.exists(snap_shot_dir):
        os.mkdir(snap_shot_dir)   
    
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)

    regions = ['us-east-1','us-east-2','us-west-1','us-west-2']
    snap_types = ['Created by CreateImage']
    for region in regions:
        out_file_name = profile + '-' + region + '-snapshot-data.txt'
        out_file = os.path.join(data_dir, out_file_name)
        if os.path.exists(out_file):
            try:
                os.remove(out_file)
            except Exception as e:
                print(str(e))
        snaps_in_region = get_snap_shots(region)
        if (len(snaps_in_region) > 0):
            print("\nSNAPS FOR REGION: " + region + '\n')
            # pp.pprint(snaps_in_region)
    
            for snap_type in snap_types:
                total_snaps,total_size,snap_info,total_cost_month = get_snaps_by_description(snap_type,snaps_in_region)
                output_snapshot_data(total_snaps,total_size,snap_info,out_file,region,total_cost_month)

if __name__ == "__main__":
    main()