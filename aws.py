__author__ = 'townsley'
import boto.ec2
import boto.ec2.elb
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScalingGroup
from boto.ec2.elb import HealthCheck
import time
import os
import os.path
import yaml

conf_file='./aws.yaml'


def load_conf(conf=conf_file):
    # global variable to hold config dict
    global C
    with open(conf, 'r') as stream:
        C = yaml.load(stream)


def ec2_connect():
    _ec2 = boto.ec2.connect_to_region(C['region'])
    return _ec2


def elb_connect():
    _elb = boto.ec2.elb.connect_to_region(C['region'])
    return _elb


def asg_connect():
    _asg = boto.ec2.autoscale.connect_to_region(C['region'])
    return _asg


def create_key_pair(_ec2):
    # massage key_dir to make it OS friendly
    C['key_dir'] = os.path.expanduser(C['key_dir'])
    C['key_dir'] = os.path.expandvars(C['key_dir'])
    if not os.path.isdir(C['key_dir']):
        os.mkdir(C['key_dir'], 0o0700)
    try:
        key = _ec2.get_all_key_pairs(keynames=[C['key_name']])[0]
    except _ec2.ResponseError as e:
        if e.code == 'InvalidKeyPair.NotFound':
            if C['debug']: print('Creating keypair:', C['key_name'])
            key = _ec2.create_key_pair(C['key_name'])
            key.save(C['key_dir'])
        else:
            raise
    if C['debug']: print('Key Pair', key.name, 'is available')


def create_sec_group(_ec2):
    try:
        group = _ec2.get_all_security_groups(groupnames=[C['sec_group_id']])[0]
    except _ec2.ResponseError as e:
        if e.code == 'InvalidGroup.NotFound':
            if C['debug']: print('Creating Security Group:', C['sec_group_id'])
            group = _ec2.create_security_group(C['sec_group_id'], 'group with ssh/http access')
        else:
            raise
    if C['debug']: print('Security Group', group, 'is available')

    for port in [C['ssh_port'], C['http_port']]:
        try:
            group.authorize('tcp', port, port, C['cidr'])
        except _ec2.ResponseError as e:
            if e.code == 'InvalidPermission.Duplicate':
                if C['debug']: print('Security Group: %s already authorized for tcp port', port)
            else:
                raise
        if C['debug']: print('Security group %s authorized for tcp port', port)


def create_instances(_ec2, count=1):
    reservation = _ec2.run_instances(C['ami'],
                                     key_name=C['key_name'],
                                     security_groups=[C['sec_group_id']],
                                     instance_type=C['instance_type'],
                                     user_data=C['user_data'],
                                     max_count=count)
    if C['debug']: print('Reservation ID = ', reservation.id)

    for instance in reservation.instances:
        while instance.state != 'running':
            if C['debug']: print('Instance ID', instance.id, 'is', instance.state, '...')
            time.sleep(5)
            instance.update()

        _ec2.create_tags(instance.id, {'Name': C['tag_name']})

        if C['debug']: print('Instance state is', instance.state)
        if C['debug']: print('Instance FQDN is', instance.public_dns_name)

    return reservation.instances


def terminate_instances_by_tag(_ec2):
    reservations = _ec2.get_all_instances(filters={'tag:Name': C['tag_name'], 'instance-state-name': 'running'})
    instances = []
    for reservation in reservations:
        for instance in reservation.instances:
            instances.append(instance.id)
        _ec2.terminate_instances(instances)
        for instance in reservation.instances:
            while instance.state != 'terminated':
                if C['debug']: print('Instance ID', instance.id, 'is', instance.state, '...')
                time.sleep(5)
                instance.update()
            if C['debug']: print('Instance', instance.id, 'is', instance.state)


def create_health_check(_elb):
    hc = HealthCheck(
        interval=C['elb_interval'],
        timeout=C['elb_timeout'],
        healthy_threshold=C['healthy_threshold'],
        unhealthy_threshold=C['unhealthy_threshold'],
        target=C['elb_target']
    )
    return hc


def create_load_balancer(_elb):
    lbs = _elb.get_all_load_balancers()
    if C['elb_name'] in lbs:
        return
    hc = create_health_check(_elb)
    zones = [C['zonea'],C['zoneb']]
    ports = [(80, 80, 'http'), (443, 443, 'tcp')]
    lb = _elb.create_load_balancer(C['elb_name'], zones, ports)
    lb.configure_health_check(hc)
    print(lb.dns_name)
    return lb


def lb_register_instances(_lb, _instances):
    i_list=[]
    for instance in instances:
        i_list.append(instance.id)
    _lb.register_instances(i_list)


def delete_load_balancer(_elb):
    lbs = _elb.get_all_load_balancers(load_balancer_names=[C['elb_name']])
    if len(lbs) > 0:
        _elb.delete_load_balancer(C['elb_name'])


def create_launch_config(_asg):
    lc = LaunchConfiguration(name=C['lc_name'], image_id=C['ami'],
                             key_name=C['key_name'],
                             security_groups=[C['sec_group_id']])
    lcs = _asg.get_all_launch_configurations(names=[C['lc_name']])
    if len(lcs) == 0:
        _asg.create_launch_configuration(lc)
    return lc


def delete_launch_config(_asg):
    lcs = _asg.get_all_launch_configurations(names=[C['lc_name']])
    if len(lcs) > 0:
        _asg.delete_launch_configuration(C['lc_name'])


def create_autoscale_group(_asg):
    lc = create_launch_config(_asg)
    ag = AutoScalingGroup(group_name=C['asg_name'], load_balancers=[C['elb_name']],
                          availability_zones=[C['zonea'],C['zoneb']],
                          launch_config=lc, min_size=C['asg_min'], max_size=C['asg_max'],
                          connection=_asg)
    ags = _asg.get_all_groups(names=[C['asg_name']])
    if len(ags) == 0:
        _asg.create_auto_scaling_group(ag)
    while [ True ]:
        ag.get_activities()
        time.sleep(5)
        print("mark")


def delete_autoscale_group(_asg):
    _asg.delete_auto_scaling_group(C['asg_name'])


def scorched_earth(_ec2, _elb, _asg):
    terminate_instances_by_tag(_ec2)
    delete_load_balancer(_elb)
    delete_autoscale_group(_asg)
    delete_launch_config(_asg)


if __name__ == "__main__":
    load_conf()

    # EC2 BLOCK
    ec2 = ec2_connect()
    # create_key_pair(ec2)
    # create_sec_group(ec2)
    # instances = create_instances(ec2, 2)

    # ELB BLOCK
    elb = elb_connect()
    # lb = create_load_balancer(elb)
    # lb_register_instances(lb, instances)

    # ASG BLOCK
    asg = asg_connect()
    # create_autoscale_group(asg)

    scorched_earth(ec2, elb, asg)


