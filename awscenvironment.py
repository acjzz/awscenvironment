#!/usr/bin/python
#------------------------------------------------------------------------------
# The MIT License (MIT)

# Copyright (c) 2014 Jordi Arnavat

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#------------------------------------------------------------------------------
import ansible.runner
from troposphere import Ref, Template
import troposphere.ec2 as ec2
import time
import argparse
import os
import json
import logging
import ConfigParser
import io

SCRIPT_NAME = 'AWScEnvironment'

logger = logging.getLogger(SCRIPT_NAME)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)

if not os.path.exists('logs'):
    os.makedirs('logs') 

if not os.path.exists('tmp'):
    os.makedirs('tmp') 

fh = logging.FileHandler('logs/awscenvironment.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)

logger.addHandler(ch)
logger.addHandler(fh)

def create_stack(stack_name,template_name, region="eu-west-1", disable_rollback="no"):
    logger.info("Creating template %s"%template_name)
    hosts = [ '127.0.0.1' ]
    inventory = ansible.inventory.Inventory(hosts)

    results = ansible.runner.Runner(
        module_name='cloudformation', 
        module_args='stack_name="%s" state=present region=%s disable_rollback=%s template=%s'%(stack_name,region,disable_rollback,template_name),
        pattern="*",
        inventory=inventory,
        transport='local'
        ).run()

    if results is None:
       print "No hosts found"
       sys.exit(1)

    for (hostname, result) in results['contacted'].items():
        if "failed" in result.keys() and result["failed"]:
            print "Failed:"
            print result["msg"]
        elif "changed" in result.keys():
            print "Changed"
            print result["output"]
        else:
            print hostname,result

class Environment():
    def __init__(self, environment, vpc_cidrblock, subnets_description, stack_description = "Created using AWSCloudFormationEnvironment"):
        self.environment = environment
        self.vpc_cidrblock = vpc_cidrblock
        self.subnets_description = subnets_description
        self.stack_description = stack_description

    def __vpc(self):
        self.vpc = self.template.add_resource(ec2.VPC(
            "%sVPC" % self.environment ,
            EnableDnsSupport = "true" ,
            CidrBlock = self.vpc_cidrblock ,
            EnableDnsHostnames = "true" ,
            Tags = [ ec2.Tag( "Name" , "%s::VPC" % self.environment ) ] + self.defaultTags
        ))

    def __subnets(self):
        self.subnets = {}
        for availability_zone, cidr in self.subnets_description.iteritems():
            self.subnets[availability_zone] = self.template.add_resource( ec2.Subnet(
                "%s%sSUBNET" % (self.environment,"".join(availability_zone.split('-'))) ,
                VpcId = Ref(self.vpc) ,
                AvailabilityZone =  availability_zone,
                CidrBlock = cidr,
                Tags = [ ec2.Tag( "Name" , "%s::%s::SUBNET" % (self.environment,availability_zone) ) ] + self.defaultTags
            ))

    def __attach_igw(self):
        self.igw = self.template.add_resource( ec2.InternetGateway(
            "%sINTERNETGATEWAY" % self.environment ,
            Tags = [ ec2.Tag( "Name" , "%s::INTERNETGATEWAY" % self.environment ) ] + self.defaultTags
        ))

        self.vpc_gateway_attachment = self.template.add_resource( ec2.VPCGatewayAttachment(
            "%sVPCGATEWAYATTACHMENT" % self.environment ,
            InternetGatewayId = Ref( self.igw ) ,
            VpcId = Ref( self.vpc ),
        ))

    def __route(self):
        self.route_table = self.template.add_resource( ec2.RouteTable(
            "%sROUTETABLE" % self.environment ,
            VpcId = Ref(self.vpc) ,
            Tags = [ ec2.Tag( "Name" , "%s::ROUTETABLE" % self.environment ) ] + self.defaultTags
        ))

        self.gwr = self.template.add_resource( ec2.Route(
            "%sGATEWAYROUTE" % self.environment ,
            DestinationCidrBlock = "0.0.0.0/0" ,
            GatewayId = Ref( self.igw ) ,
            RouteTableId = Ref( self.route_table ),
        ))

        for zone,ref in self.subnets.iteritems():
            self.subnet_route_table_association = self.template.add_resource( ec2.SubnetRouteTableAssociation( 
                "%s%sSUBNETROUTETABLEASSOCIATION" % (self.environment,"".join(zone.split('-'))),
                RouteTableId= Ref(self.route_table),
                SubnetId= Ref(ref),
            ) )

    def create(self):
        self.template = Template()
        self.template.add_description( self.stack_description )
        created = time.strftime( "%Y-%m-%d %H:%M:%S" )
        self.defaultTags = [ ec2.Tag( "Environment" , self.environment ) , ec2.Tag( "Created" ,  created ) ]
        self.__vpc()
        self.__subnets()
        self.__attach_igw()
        self.__route()

    def save(self, filename):
        f = open( filename,"w")
        f.write(self.template.to_json())
        f.close()



def main():
    parser = argparse.ArgumentParser()
    

    parser.add_argument('-s', '--stack', 
                        help='Stack name',
                        required=True)
    parser.add_argument('-e', '--environment', 
                        help='Environment name',
                        required=True)
    parser.add_argument('-c', '--config_file', 
                        help='Config File of cidr specification',
                        required=True)

    args = parser.parse_args()

    logger.info('Executing %s'%args)
    logger.info('Creating cloudformation template')

    config = ConfigParser.RawConfigParser(allow_no_value=True)
    config.read(args.config_file)
    regions = ['us-east-1','us-east-2','us-west-1','eu-west-1','ap-southeast-1','ap-southeast-2','ap-northeast-1','sa-east-1']
    
    if config.sections()[0] not  in regions:
        logger.error("%s should be an amazon region like: %s"%(config.sections()[0],', '.join(regions)))
        sys.exit(1)

    region = config.sections()[0]
    vpc_cidrblock = config.get(region,'vpc_cidrblock')

    subnets = {}
    for item in config.items(region):
        if item[0].startswith(region):
            subnets[item[0]] = item[1]

    env = Environment(args.environment,vpc_cidrblock,subnets)
    env.create()
    env.save(os.path.join("tmp","cloudformation"))
    logger.info('Creating Stack: %s'%args.stack)
    create_stack(args.stack,os.path.join("tmp","cloudformation"), region=region, disable_rollback="no")


if __name__ == '__main__':
    main()