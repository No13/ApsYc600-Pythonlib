'''
Module to send data to domoticz
'''
# pylint: disable=E0401
import urequests
import ubinascii

class Domoticz:
    '''
    Domoticz Client
    '''
    headers = ""
    url = ""

    def __init__(self, url, username, password):
        '''
        Set local vars
        '''
        base64pass = ubinascii.b2a_base64(username+":"+password).decode("utf-8").rstrip()
        self.headers = {'Authorization':'Basic '+base64pass}
        self.url = url

    def send_data(self, data):
        '''
        Send data
        data = {'idx': value, 'idx': value}
        '''
        result = []
        try:
            for key, val in data.items():
                url = self.url + "/json.htm?type=command&param=udevice&idx="
                url += key + "&nvalue=0&svalue=" + str(val)
                client = urequests.get(url, headers=self.headers)
                result.append(client.status_code)
                client.close()
        except Exception as domoticz_error:
            print("Error in domo", domoticz_error)
            result.append('err')
        return result
