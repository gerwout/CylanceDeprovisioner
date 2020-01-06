import jwt
import uuid
import requests
# needed so that cx_freeze knows that requests uses this library as well
from multiprocessing import Queue
import json
from datetime import datetime, timedelta

class cylance():

    access_token = ""
    cylance_app_host = ""
    cylance_app_id = ""
    cylance_tenant_id = ""
    cylance_app_secret = ""

    def __init__(self, host, app_id, tenant_id, app_secret):
        self.cylance_app_host = host
        self.cylance_app_id = app_id
        self.cylance_tenant_id = tenant_id
        self.cylance_app_secret = app_secret

    def __authenticate_to_cylance(self, scope):
        # access token will be valid for 1 minute
        timeout = 60
        now = datetime.utcnow()
        timeout_datetime = now + timedelta(seconds=timeout)
        epoch_time = int((now - datetime(1970, 1, 1)).total_seconds())
        epoch_timeout = int((timeout_datetime - datetime(1970, 1, 1)).total_seconds())
        jti_val = str(uuid.uuid4())

        AUTH_URL = self.cylance_app_host + "/auth/v2/token"

        claims = {
            "exp": epoch_timeout,
            "iat": epoch_time,
            "iss": "http://cylance.com",
            "sub": self.cylance_app_id,
            "tid": self.cylance_tenant_id,
            "jti": jti_val,
            "scp": scope
        }

        # encoded is basically your auth token
        encoded = jwt.encode(claims, self.cylance_app_secret, algorithm='HS256').decode('utf-8')
        payload = {"auth_token": encoded}
        headers = {"Content-Type": "application/json; charset=utf-8"}
        try:
            resp = requests.post(AUTH_URL, headers=headers, data=json.dumps(payload), timeout=20)
        except:
            # logger.info('Cylance auth token call failed!', 'plugin')
            # if the Cylance API experiences troubles, we return that it is down
            return "DOWN"
        if (resp.status_code == 200):
            self.access_token = json.loads(resp.text)['access_token']
            return True
        else:
            return False

    def delete_device(self, id):
        self.__authenticate_to_cylance("device:delete")
        url = self.cylance_app_host + "/devices/v2/"
        headers = {"Content-Type": "application/json; charset=utf-8", "Authorization": "Bearer " + self.access_token}
        payload = {}
        payload["device_ids"] = [id]
        try:
            resp = requests.delete(url, headers=headers, data=json.dumps(payload))
            if resp.status_code == 202:
                return True
            else:
                return False
        except:
            return False

    # needs device:list scope
    def get_all_devices(self, page=1, merge_with=None):
        self.__authenticate_to_cylance("device:list")
        url = self.cylance_app_host + "/devices/v2/?page="+str(page)+"&page_size=1000"
        headers = {"Content-Type": "application/json; charset=utf-8", "Authorization": "Bearer " + self.access_token}
        try:
            resp = requests.get(url, headers=headers, timeout=2)
        except:
            # if the Cylance API experiences troubles, we assume that you are compliant to avoid an availability concern
            return True
        try:
            ret_value = resp.json()
            current_page = ret_value['page_number']
            total_pages = ret_value['total_pages']
            systems = ret_value['page_items']
            if merge_with is not None:
                systems = systems + merge_with
            if current_page < total_pages:
                systems = self.get_all_devices(page=page+1, merge_with=systems)

            return systems
        except:
            # i.e. device id not found
            return False

    def get_device_details(self, device_id):
        self.__authenticate_to_cylance("device:read")
        url = self.cylance_app_host + "/devices/v2/" + device_id
        headers = {"Content-Type": "application/json; charset=utf-8", "Authorization": "Bearer " + self.access_token}
        try:
            resp = requests.get(url, headers=headers, timeout=2)
        except:
            # if the Cylance API experiences troubles, we assume that you are compliant to avoid an availability concern
            return True
        try:
            return resp.json()
        except:
            # i.e. device id not found
            return False


    def check_mac_address_registered(self, mac_address):
        self.__authenticate_to_cylance("device:read")
        # lets unify the format first
        mac_address = mac_address.upper()
        mac_address = ':'.join([i + j for i, j in zip(mac_address[::2], mac_address[1::2])])
        mac_url = self.cylance_app_host + "/devices/v2/macaddress/" + mac_address
        headers = {"Content-Type": "application/json; charset=utf-8", "Authorization": "Bearer " + self.access_token}

        try:
            resp = requests.get(mac_url, headers=headers, timeout=2)
        except:
            # if the Cylance API experiences troubles, we assume that you are compliant to avoid an availability concern
            return True

        machines = json.loads(resp.text)
        if isinstance(machines, list):
            for machine in machines:
                state = machine["state"]
                is_safe = machine["is_safe"]
                name = machine["name"]
                if state == "Online" and is_safe:
                    return True
            return False
        else:
            return False