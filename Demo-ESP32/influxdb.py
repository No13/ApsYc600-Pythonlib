'''
InfluxDB Client
'''
# pylint: disable=E0401
import urequests


class InfluxDBClient:
    '''
    InfluxDB Client
    '''
    url = ''

    def __init__(self, url, db_name, username, token):
        '''
        Set local var for url
        '''
        self.url = url+'/write?db='+db_name+'&u='+username+'&p='+token
        # To be implemented:
        # https://docs.influxdata.com/influxdb/v1.8/tools/api/#apiv2write-http-endpoint

    def write(self, bucket, data):
        '''
        Post data
        '''
        influx_data = ""
        result = False
        http_client = ""
        for key, val in data.items():
            influx_data += key+'='+str(val)+','
        try:
            http_client = urequests.post(
                self.url,
                data=bucket+' '+influx_data[:-1])
            result = http_client.status_code
            http_client.close()
        except Exception as influx_error:
            print("Error in influx", influx_error)
            result = "err"

        return result

    def set_url(self, url, db_name, username, token):
        '''
        Set local var for url
        '''
        self.url = url+'/write?db='+db_name+'&u='+username+'&p='+token
