import os
import json
import boto3
import logging
import urllib.request, urllib.error, urllib.parse

# Customize the tags you'd like the function to filter against when getting managed prefix lists
FILTER_TAGS = {'AutoUpdate': 'True', 'Updater': 'Cloudflare'}

# Do not change unless Cloudflare changes their IPs endpoint
# https://api.cloudflare.com/#cloudflare-ips-cloudflare-ip-details
CLOUDFLARE_URL = 'https://api.cloudflare.com/client/v4/ips'

# Set the DEBUG env to 'True' to see debug output in logs
DEBUG = os.environ['DEBUG'] == 'True'
# Set the DRY_RUN env to 'True' if you don't want to actually perform actions
DRY_RUN = os.environ['DRY_RUN'] == 'True'

# The list of statuses a managed prefix list can have for it to be considered editable
ACCEPTED_STATUSES = ['create-complete', 'modify-complete', 'restore-complete']

def lambda_handler(event, context):
    if len(logging.getLogger().handlers) > 0:
        logging.getLogger().setLevel(logging.ERROR)
    else:
        logging.basicConfig(level=logging.INFO)
    
    try:
        if DEBUG:
            logging.getLogger().setLevel(logging.DEBUG)
    except KeyError:
        pass
    
    lists = get_managed_prefix_lists()
    filtered_lists = filter_managed_prefix_lists(lists)
    ip_list = get_cloudflare_ips()
    processed_lists_count = process_filtered_managed_lists(filtered_lists, ip_list)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Updated {} lists'.format(processed_lists_count))
    }

def get_managed_prefix_lists():
    logging.info('Getting prefix lists matching {}'.format(FILTER_TAGS))
    
    client = boto3.client('ec2')
    lists = client.describe_managed_prefix_lists(
        DryRun=DRY_RUN,
        Filters=get_filter_tags())
        
    logging.debug('Response: {}'.format(lists))
    logging.info('Found {} lists matching the criteria'.format(len(lists['PrefixLists'])))
    
    return lists['PrefixLists']
    
def filter_managed_prefix_lists(lists):
    lists_by_status = {}
    filtered_lists = list()
    
    for list_entry in lists:
        if list_entry['State'] not in lists_by_status:
            lists_by_status[list_entry['State']] = list()
            
        lists_by_status[list_entry['State']].append(list_entry)
        
        if list_entry['State'] in ACCEPTED_STATUSES:
            filtered_lists.append(list_entry)
            
    if DEBUG:
        for key, lists in lists_by_status.items():
            logging.debug('Lists with status {}:'.format(key))
            
            for list_entry in lists:
                logging.debug('- {}'.format(list_entry['PrefixListId']))
            
    logging.info('Found {} viable lists out of a total of {}'.format(len(filtered_lists), len(lists)))
    
    return filtered_lists
    
def get_cloudflare_ips():
    logging.info('Updating IP list from {}'.format(CLOUDFLARE_URL))

    response = urllib.request.urlopen(CLOUDFLARE_URL)
    ip_json = json.loads(response.read())
    
    logging.debug('Response: {}'.format(ip_json))
    
    if ip_json['success'] != True:
        raise Exception('Failed to retrieve IP list: {}'.format(ip_json))

    return ip_json
    
def process_filtered_managed_lists(filtered_lists, ip_list):
    client = boto3.client('ec2')
    
    current_ip_list = ip_list['result']['ipv4_cidrs']
    
    logging.info('Updating lists')
    logging.debug('Cloudflare IPv4 CIDRs: {}'.format(current_ip_list))
    
    updated_count = 0
    
    for list_entry in filtered_lists:
        logging.debug('Processing {}'.format(list_entry['PrefixListId']))
        
        list_entries = list()
        response = client.get_managed_prefix_list_entries(
            DryRun=DRY_RUN,
            PrefixListId=list_entry['PrefixListId'])
        
        logging.debug('Response: {}'.format(response))
        
        for entry in response['Entries']:
            list_entries.append(entry['Cidr'])
            
        list_version = list_entry['Version']
        logging.debug('Current list version: {}'.format(list_version))
            
        new_entries = list()
        obsolete_entries = list()
        
        for entry in list_entries:
            if entry not in current_ip_list:
                obsolete_entries.append(entry)
                
        for entry in current_ip_list:
            if entry not in list_entries:
                new_entries.append(entry)
                
        logging.debug('New entries: {}'.format(new_entries))
        logging.debug('Obsolete entries: {}'.format(obsolete_entries))
        logging.info('Found {} new entries, {} obsolete entries and {} unchanged entries'.format(len(new_entries), len(obsolete_entries), clamp((len(list_entries) - len(new_entries) - len(obsolete_entries)), 0, 200)))
        
        if len(new_entries) == 0 and len(obsolete_entries) == 0:
            logging.info('Skipping since already up to date')
            return 0
        
        new_entries_formatted = list()
        obsolete_entries_formatted = list()
        
        for entry in new_entries:
            new_entries_formatted.append({'Cidr': entry, 'Description': ''})
            
        for entry in obsolete_entries:
            obsolete_entries_formatted.append({'Cidr': entry})
        
        client.modify_managed_prefix_list(
            DryRun=DRY_RUN,
            PrefixListId=list_entry['PrefixListId'],
            CurrentVersion=list_version,
            AddEntries=new_entries_formatted,
            RemoveEntries=obsolete_entries_formatted)
        
        updated_count = updated_count + 1
        logging.info('Updated {}'.format(list_entry['PrefixListId']))
        
    return len(updated_count)

def get_filter_tags():
    filters = list()
    
    for key, value in FILTER_TAGS.items():
        filters.extend(
            [
                {'Name': 'tag-key', 'Values': [ key ]},
                {'Name': 'tag-value', 'Values': [ value ]}
            ]
        )
        
    return filters
    
def clamp(num, min_value, max_value):
    return max(min(num, max_value), min_value)
