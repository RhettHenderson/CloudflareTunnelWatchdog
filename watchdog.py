import requests
import time

#Cloudflare API Credentials
API_TOKEN='123456789abcdef'
ZONE_ID='123456789abcdef'
RECORD_NAMES = [
    'healthy.example.com',
    'test.example.com'
    ]

#Tunnels
PRIMARY_TUNNEL='abcdefg-1234-abcd-efgh-123456789abc.cfargotunnel.com'
BACKUP_TUNNEL='abcdefg-1234-abcd-efgh-123456789abc.cfargotunnel.com'

#Check the health of the main tunnel
PRIMARY_HEALTHCHECK_URL = 'healthcheckURL'
HEALTHY_CHECK_INTERVAL = 180
CHECK_INTERVAL = 30
FAIL_THRESHOLD = 3

#Cloudflare API Headers
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

#Gets the cloudflare DNS record and its current target
def get_record_id(record_name, output=True):
    url = f'https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records?type=CNAME&name={record_name}'
    if output:
        print("Requesting URL:", url)
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    records = resp.json()['result']
    if not records:
        raise Exception(f"No CNAME record found for {record_name}")
    return records[0]['id'], records[0]['content']

#Current CNAME in use
_, CURRENT_CNAME = get_record_id(RECORD_NAMES[0], False)

def update_cname(target):
    for name in RECORD_NAMES:
        data = {
        "type": "CNAME",
        "name": name,
        "content": target,
        "ttl": 1,
        "proxied": True
    }
        record_id, _ = get_record_id(name)
        url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{record_id}"

        resp = requests.put(url, headers=HEADERS, json=data)
        resp.raise_for_status()
        #CURRENT_CNAME = target
        print(f"Updated URL for {name} with code ", resp.status_code)
        print()


def primary_up():
    try:
        r = requests.get(PRIMARY_HEALTHCHECK_URL, timeout = 3)
        return r.status_code == 200
    except requests.RequestException:
        return False

if __name__ == "__main__":
    fail_count = 0
    print("Starting Cloudflare Tunnel Watchdog...\n")
    while True:
        _, CURRENT_CNAME = get_record_id(RECORD_NAMES[0], False)
        now = time.asctime(time.localtime())
        try:
            if primary_up():
                #Case: Primary tunnel is up but current tunnel is the backup
                if CURRENT_CNAME != PRIMARY_TUNNEL:
                    print(now, "Primary tunnel back online, switching back.\n")
                    update_cname(PRIMARY_TUNNEL)
                #This should run every time, even if we just switched back
                print(now, "Primary tunnel is online\n")
                fail_count = 0
                time.sleep(HEALTHY_CHECK_INTERVAL)
            elif CURRENT_CNAME == PRIMARY_TUNNEL:
                #Case: Primary tunnel has failed a healthcheck but we haven't swapped over yet
                fail_count += 1
                message = f", retrying in {CHECK_INTERVAL} seconds" if fail_count < FAIL_THRESHOLD else ""
                print(now, f"Primary tunnel has failed a healthcheck {fail_count}/{FAIL_THRESHOLD} times{message}")

                #Don't wait if we've already reached the threshold, but if we haven't, wait
                if fail_count >= FAIL_THRESHOLD:
                    print(now, "Maximum number of failures reached, switching to secondary tunnel\n")
                    update_cname(BACKUP_TUNNEL)
                else:
                    time.sleep(CHECK_INTERVAL)
            else:
                #Case: primary tunnel is down and we've already switched
                fail_count = 0
                print(now, "Primary tunnel still down, backup tunnel active")
                #Still waiting the longer time because it doesn't make a big difference being on the backup
                time.sleep(HEALTHY_CHECK_INTERVAL)
        except Exception as e:
            print(f"Error: {e}")
