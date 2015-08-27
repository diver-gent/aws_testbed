__author__ = 'townsley'
import boto.ec2
import time

ec2 = boto.ec2.connect_to_region('us-west-2')
reservation = ec2.run_instances(image_id='ami-29ebb519',
                                key_name='devenv-key',
                                instance_type='t2.micro',
                                security_group_ids=['devenv-sg'])
print("Reservation ID = ", reservation.id)
instance = reservation.instances[0]
while instance.state != "running":
    print "Instance state is", instance.state, "..."
    time.sleep(5)
    instance.update()
print "Instance state is", instance.state, "!"
print "Instance ID is", instance.id
print instance.public_dns_name

time.sleep(60)

ec2.terminate_instances(instance.id)

