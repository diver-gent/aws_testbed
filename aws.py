__author__ = 'townsley'
import boto.ec2
import time
import os
import os.path
import yaml

conf_file='./aws.yaml'


def setup(conf=conf_file):
    # global variable to hold config data
    global c
    with open(conf, 'r') as stream:
        c = yaml.load(stream)

    # massage key_dir to make it OS friendly
    c['key_dir'] = os.path.expanduser(c['key_dir'])
    c['key_dir'] = os.path.expandvars(c['key_dir'])
    if not os.path.isdir(c['key_dir']):
                    os.mkdir(c['key_dir'], 0700)


def create_key_pair(ec2):
    try:
        key = ec2.get_all_key_pairs(keynames=[c['key_name']])[0]
    except ec2.ResponseError, e:
        if e.code == 'InvalidKeyPair.NotFound':
            if c['debug']: print 'Creating keypair: %s' % c['key_name']
            key = ec2.create_key_pair(c['key_name'])
            key.save(c['key_dir'])
        else:
            raise
    if c['debug']: print 'Key Pair', key.name, 'is available'


def create_sec_group(ec2):
    try:
        group = ec2.get_all_security_groups(groupnames=[c['sec_group_id']])[0]
    except ec2.ResponseError, e:
        if e.code == 'InvalidGroup.NotFound':
            if c['debug']: print 'Creating Security Group: %s' % c['sec_group_id']
            group = ec2.create_security_group(c['sec_group_id'], 'group with ssh/http access')
        else:
            raise
    if c['debug']: print 'Security Group', group, 'is available'

    for port in [c['ssh_port'], c['http_port']]:
        try:
            group.authorize('tcp', port, port, c['cidr'])
        except ec2.ResponseError, e:
            if e.code == 'InvalidPermission.Duplicate':
                if c['debug']: print 'Security Group: %s already authorized for tcp port', port
            else:
                raise
        if c['debug']: print 'Security group %s authorized for tcp port', port


def create_tags(ec2):
    ec2.create_tags([instance.id], {'Name': c['tag_name']})


def create_instances(count=1):

    ec2 = boto.ec2.connect_to_region(c['region'])Re

    for i in range(0, count):
        create_key_pair(ec2)
        create_sec_group(ec2)
        reservation = ec2.run_instances(c['drupal_ami'],
                                        key_name=c['key_name'],
                                        security_groups=[c['sec_group_id']],
                                        instance_type=c['instance_type'],
                                        user_data=c['user_data'])
        if c['debug']: print 'Reservation ID = ', reservation.id

        instance = reservation.instances[0]
        while instance.state != 'running':
            if c['debug']: print 'Instance ID', instance.id, 'is', instance.state, '...'
            time.sleep(5)
            instance.update()

        create_tags(ec2)

        if c['debug']: print 'Instance state is', instance.state
        if c['debug']: print 'Instance FQDN is', instance.public_dns_name



# ec2.terminate_instances(instance.id)
# while instance.state != 'terminated':
#     print 'Instance state is', instance.state, '...'
#     time.sleep(5)
#     instance.update()
# print 'Instance state is', instance.state, '!'

if __name__ == "__main__":
    setup()
    create_instances()


