## AWScEnvironment stands for *AWS Cloud Environment*

It is a python script that helps you to create new enironments in an automated way.

### How does it work?
By now it just creates a base environment with vpc, subnets, internet gateway, routes and all the basic stuff to just start launching instances in a new and clean vpc.

### Dependencies:

- [boto](https://github.com/boto/boto)
- [ansible](https://github.com/ansible/ansible)
- [troposphere](https://github.com/cloudtools/troposphere)

### Getting Started

First of all, in order to use this script, you have to provide your credentials to boto. [Please follow this link to do it](https://code.google.com/p/boto/wiki/BotoConfig)

And then just run the script from the command line:
```
python awscenvironment.py -h
```

### Notes

In order to create a vpc you have to specify a config file with the next format:

```
[eu-west-1]
vpc_cidrblock = 10.0.0.0/16
eu-west-1a = 10.0.0.0/18
eu-west-1b = 10.0.64.0/18
eu-west-1c = 10.0.128.0/18
```