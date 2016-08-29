#!/usr/bin/env python

import os
import sys
import django


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'caselink.settings')

django.setup()

from django.db import transaction

from caselink.tasks.common import *

def run():
    print('Loading Error')
    load_error()

    print('Loading Project')
    load_project()

    print('Loading Manual Cases')
    load_manualcase()

    print('Loading Linkage')
    load_linkage()

    print('Loading Auto Cases')
    load_autocase()

    print('Loading Auto failure and bugs')
    load_failure()

    print('Checking for errors...')
    init_error_checking()

if __name__ == '__main__':
    run()
