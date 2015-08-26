__author__ = 'townsley'
import boto.ec2

ec2 = boto.ec2.connect_to_region('us-west-2')
reservation = ec2.run_instances(image_id='ami-29ebb519',
                                key_name='devenv-key',
                                instance_type='t2.micro',
                                security_group_ids=['devenv-sg'])

print(ec2.get_all_instances())
print(reservation)
print(reservation.id)

# Wait a minute or two while it boots
for r in ec2.get_all_instances():
    print(r)
    if r.id == reservation.id:
        reservations = ec2.get_all_instances(instance_ids=[reservation.id])
        i = reservations[0].instances[0]
        print(i.public_dns_name)
        break

print(r.instances[0].public_dns_name)
