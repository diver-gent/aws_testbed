__author__ = 'townsley'
import boto.ec2
import time
import os
import os.path

region = 'us-west-2'
ami = 'ami-29ebb519'
instance_type = 't2.micro'
key_name = 'devenv_key'
key_extension = '.pem'
key_dir = '~/.ssh'
security_group_id = 'devenv_sg'
ssh_port = 22
cidr = '0.0.0.0/0'
user_data = None
cmd_shell  =True
login_user = 'ubuntu'
ssh_passwd = None

ec2 = boto.ec2.connect_to_region(region)

try:
    key = ec2.get_all_key_pairs(keynames=[key_name])[0]
except ec2.ResponseError, e:
    if e.code == 'InvalidKeyPair.NotFound':
        print 'Creating keypair: %s' % key_name
        # Create an SSH key to use when logging into instances.
        key = ec2.create_key_pair(key_name)

        # Make sure the specified key_dir actually exists.
        # If not, create it.
        key_dir = os.path.expanduser(key_dir)
        key_dir = os.path.expandvars(key_dir)
        if not os.path.isdir(key_dir):
            os.mkdir(key_dir, 0700)

        # AWS will store the public key but the private key is
        # generated and returned and needs to be stored locally.
        # The save method will also chmod the file to protect
        # your private key.
        key.save(key_dir)
    else:
        raise
print 'Key Pair', key_name, 'is available.'
print

try:
    group = ec2.get_all_security_groups(groupnames=[security_group_id])[0]
except ec2.ResponseError, e:
    if e.code == 'InvalidGroup.NotFound':
        print 'Creating Security Group: %s' % security_group_id
        # Create a security group to control access to instance via SSH.
        group = ec2.create_security_group(security_group_id, 'group with ssh access')
    else:
        raise
print 'Security Group', security_group_id, 'is available.'
print

try:
    group.authorize('tcp', ssh_port, ssh_port, cidr)
except ec2.ResponseError, e:
    if e.code == 'InvalidPermission.Duplicate':
        print 'Security Group: %s already authorized' % security_group_id
    else:
        raise
print 'Security group', security_group_id, 'authorized for:'
print '\ttcp'
print '\tssh'
print '\tssh port', ssh_port
print '\tcidr', cidr
print

reservation = ec2.run_instances(ami,
                                key_name=key_name,
                                security_groups=[security_group_id],
                                instance_type=instance_type,
                                user_data=user_data)

print 'Reservation ID = ', reservation.id
instance = reservation.instances[0]
print 'Instance ID is', instance.id
print

while instance.state != 'running':
    print 'Instance state is', instance.state, '...'
    time.sleep(5)
    instance.update()
print 'Instance state is', instance.state
print

print 'Instance FQDN is', instance.public_dns_name
print

# ec2.terminate_instances(instance.id)
# while instance.state != 'terminated':
#     print 'Instance state is', instance.state, '...'
#     time.sleep(5)
#     instance.update()
# print 'Instance state is', instance.state, '!'


