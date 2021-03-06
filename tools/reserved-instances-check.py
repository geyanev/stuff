#!/usr/bin/env python

# Copyright 2012, 42Lines, Inc.
# Original Author: Jim Browne
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict
import boto
import boto.ec2
from operator import attrgetter
from optparse import OptionParser
from datetime import datetime
# apt-get install python-dateutil
from dateutil.parser import *
from dateutil.tz import *
from dateutil.relativedelta import *

VERSION = "1.0"
IMONTH = 3
RDAYS = 15
usage = """%prog [options]

Compare purchased reserved instances against running instances and
offer advice on current coverage.  Optionally report on running
instances and purchased reservations.

"""


def instance_string(instance, options, verbose=False):
    output = "id {0.id}".format(instance)

    if verbose:
        fmt = " region {0.region} placement {0.placement}"
        fmt += " type {0.instance_type} state {0.state}"
        output += fmt.format(instance)

    output += " start {0.launch_time:.16}".format(instance)

    if options.itag:
        value = instance.tags.get(options.itag, '')
        if value:
            output += " ({0:.32})".format(value)

    return output


def reservation_timing(reservation):
    utcnow = datetime.now(tzutc())
    start = parse(reservation.start)

    elapsed = utcnow - start
    duration = int(reservation.duration) / (60 * 60 * 24)
    left = duration - elapsed.days

    return (duration, elapsed.days, left)


def reservation_left(reservation):
    timing = reservation_timing(reservation)

    return timing[2]


def reservation_string(reservation, verbose=False):

    output = ''
    if verbose:
        fmt = "id {0.id} state {0.state} region {0.region}"
        fmt += " place {0.availability_zone} type {0.instance_type}"
        fmt += " "
        output += fmt.format(reservation)

    timing = reservation_timing(reservation)

    fmt = "count {0.instance_count} start {0.start:.16} os_type {1} duration {2}"
    fmt += " elapsed {3} left {4}"
    output += fmt.format(reservation, reservation.description, timing[0], timing[1], timing[2])

    return output


def check_zone_use(options, instances, purchases, where):
    if options.debug:
        print 'instances {0}'.format(instances)
        print 'purchases {0}'.format(purchases)

    advice = ''
    types = instances.keys() + purchases.keys()

    for itype in sorted(set(types)):
        inst_count = 0
        if itype in instances:
            inst_count = len(instances[itype])

        pur_count = 0
        if itype in purchases:
            for r in purchases[itype]:
                pur_count += r.instance_count

        delta = inst_count - pur_count
        dfmt = '  Type {0} Reservations {1} Instances {2} Delta {3}'
        if not options.quiet:
            print dfmt.format(itype, pur_count, inst_count, delta)

        if delta < 0:
            advice += '{0} unused reservation(s) in {1}\n'.format(-1 * delta,
                                                                   where)
            advice += 'Use --rdetail to see reservation details\n'
            advice += '\n'
        elif delta > 0:
            insts = instances[itype]

            # Instances running more than three months are candidates
            testdate = (datetime.now(tzutc()) +
                        relativedelta(months=-1 * options.imonth))
            teststring = testdate.isoformat()
            candidates = [i for i in insts if i.launch_time < teststring]
            sortcand = sorted(candidates, key=attrgetter('launch_time'))

            # Assume purchases cover the oldest instances
            suggest = sortcand[pur_count:]

            if suggest:
                advfmt = '{0} candidate(s) for a {1} reservation purchase in {2}\n'
                advice += advfmt.format(len(suggest), itype, where)
                sstrings = [instance_string(s, options) for s in suggest]
                advice += '\n'.join(sstrings)
                advice += '\n\n'

        if pur_count:
            expiring = [r for r in purchases[itype]
                          if reservation_left(r) < options.rdays]
            if expiring:
                advfmt = '{0} reservations(s) about to expire in {1}\n'
                advice += advfmt.format(len(expiring), where)
                rstrings = [reservation_string(r, options) for r in expiring]
                advice += '\n'.join(rstrings)
                advice += '\n\n'

        if options.idetail and inst_count and not options.quiet:
            insts = instances[itype]
            istrings = [instance_string(i, options) for i in insts]
            output = ',\n      '.join(istrings)
            print "    Instances:\n      " + output

        if options.rdetail and pur_count and not options.quiet:
            rsvs = purchases[itype]
            rstrings = [reservation_string(r) for r in rsvs]
            output = ',\n      '.join(rstrings)
            print "    Reservations:\n      " + output

    return advice


def check_reservation_use(options, running_instances, reserved_purchases):
    if options.debug:
        print 'running instances %s' % running_instances
        print 'reserved purchases %s' % reserved_purchases

    advice = ''

    inst_acct = running_instances
    pur_acct = reserved_purchases
    regions = sorted(list(set(inst_acct.keys() + pur_acct.keys())))
    for region_name in regions:
        inst_reg = {}
        if region_name in running_instances:
            inst_reg = running_instances[region_name]
            pur_reg = {}

        if region_name in reserved_purchases:
            pur_reg = reserved_purchases[region_name]

        zones = sorted(set(inst_reg.keys() + pur_reg.keys()))
        for zone in zones:
            if not options.quiet:
                print 'Zone: %s' % zone
            inst_zone = {}
            pur_zone = {}
            if zone in inst_reg:
                inst_zone = inst_reg[zone]
            if zone in pur_reg:
                pur_zone = pur_reg[zone]
 
            wherefmt = 'region {0} zone {1}'
            where = wherefmt.format(region_name, zone)
            advice += check_zone_use(options, inst_zone, pur_zone, where)
            if not options.quiet:
                print

    return advice


def reserved_compare(options):
    """
    Will compare running instances to purchased reservations across
    all EC2 regions for all of the accounts supplied.

    :type accounts: dict
    """
    running_instances = defaultdict(dict)
    reserved_purchases = defaultdict(dict)
    regions = boto.ec2.regions()
    good_regions = [r for r in regions if r.name not in ['us-gov-west-1',
                                                         'cn-north-1']]
    for region in good_regions:
        if options.trace:
            print "  Scanning region {0}".format(region.name)
        conn = region.connect()
        filters = {'instance-state-name': 'running'}
        zones = defaultdict(dict)

        if options.trace:
            print "    Fetching running instances"
        reservations = conn.get_all_instances(filters=filters)
        for reservation in reservations:
            for inst in reservation.instances:
                if options.debug:
                    print instance_string(inst, options, verbose=True)
                if inst.state != 'running':
                    if options.debug:
                        print "Skipp {0.id} state {0.state}".format(inst)
                    continue
                if inst.instance_type not in zones[inst.placement]:
                    zones[inst.placement][inst.instance_type] = []
                zones[inst.placement][inst.instance_type].append(inst)

        if zones:
            running_instances[region.name] = zones

        purchased = defaultdict(dict)
        if options.trace:
            print "    Fetching reservations"

        reserved = conn.get_all_reserved_instances()
        for r in reserved:
            if options.debug:
                print reservation_string(r, verbose=True)
            if r.state != 'active':
                continue
            if r.instance_type not in purchased[r.availability_zone]:
                purchased[r.availability_zone][r.instance_type] = [r]
            else:
                purchased[r.availability_zone][r.instance_type].append(r)

        if purchased:
            reserved_purchases[region.name] = purchased

    return check_reservation_use(options, running_instances,
                                 reserved_purchases)

if __name__ == '__main__':
    import sys

    # Need get_all_instance filter option starting with Boto 2.0
    desired = '2.0'
    try:
        from pkg_resources import parse_version
        if parse_version(boto.__version__) < parse_version(desired):
            print 'Boto version %s or later is required' % desired
            print 'Try: sudo easy_install boto'
            sys.exit(-1)
    except (AttributeError, NameError):
        print 'Boto version %s or later is required' % desired
        print 'Try: sudo easy_install boto'
        sys.exit(-1)

    parser = OptionParser(version=VERSION, usage=usage)
    parser.add_option("--imonth",
                      help="Age in months before an instance is considered" +
                      " for a reservation (default %default)",
                      default=IMONTH,
                      type="int", dest="imonth")
    parser.add_option("--idetail",
                      help="Print detailed information about instances",
                      action="store_true", dest="idetail")
    parser.add_option("--itag",
                      help="Print specified tag for each instance",
                      dest="itag")
    parser.add_option("--rdays",
                      help="Warn about reservations with less than RDAYS" +
                      " left (default %default)",
                      default=RDAYS,
                      type="int", dest="rdays")
    parser.add_option("--rdetail",
                      help="Print detailed information about reserved" +
                      " instances",
                      action="store_true", dest="rdetail")
    parser.add_option("--quiet",
                      help="Only print advice",
                      action="store_true", dest="quiet")
    parser.add_option("--debug",
                      help="Emit copious information to aid script debugging",
                      action="store_true", dest="debug")
    parser.add_option("--trace",
                      help="Trace execution steps",
                      action="store_true", dest="trace")

    (options, args) = parser.parse_args()

    if options.debug:
        options.trace = 1

    advice = reserved_compare(options)

    print
    print "Advice based on current data:"
    print
    print advice
