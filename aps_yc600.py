'''
Library to communicate with YC600 inverters
Should work with QS1 too (num_panels = 4).
Based on work from:
- https://github.com/patience4711
- https://github.com/kadzsol

I'm trying to keep this compatible with micropython for ESP32 & python3-serial
'''
import time

class ApsYc600:
    '''
    Class to communicate with YC600 inverters
    '''

    # struct to store all inverter data
    inv_data = []

    # identification for this ECU / controller
    controller_id = ""

    # Serial handles
    reader = None
    writer = None
    system_type = None

    # History data to detect inverter resets
    energy_data = []

    ### Internal helper fuctions

    def __init__(self, reader, writer, controller_id='D8A3011B9780'):
        '''
        Create controller, default controller ID is supplied
        '''
        if len(controller_id) != 12:
            raise Exception('Controller ID must be 12 hex characters')
        self.controller_id = controller_id
        self.reader = reader
        self.writer = writer

        # Try and test the reader for 'in_waiting' function
        if 'in_waiting' in dir(self.reader):
            print('Found python3-serial module')
            self.system_type = 'python3-serial'
        else:
            print('Only using read/write (micropython)')
            self.system_type = 'micropython'

    @staticmethod
    def __reverse_byte_str(in_str):
        '''
        Reverse input bytes (0123 -> 2301)
        Needs even number of characters
        '''
        if len(in_str) % 2 > 0:
            raise Exception('Input is not an even number of characters')
        out_str = ""
        for i in range(len(in_str), 1, -2):
            out_str = ''.join((out_str, in_str[i-2], in_str[i-1]))
        return out_str

    @staticmethod
    def __crc(in_str):
        '''
        Calculate CRC
        Input: string containing hex characters
        Output: hex value
        '''
        if len(in_str) % 2 > 0:
            raise Exception('Input is not an even number of characters')
        crc_res = 0
        for i in range(0, len(in_str), 2):
            # Calculate crc
            crc_res = crc_res ^ int(in_str[i:i+2], 16)
        # Return as hex value
        return hex(crc_res)

    def __crc_check(self, in_str):
        '''
        Check CRC in message
        '''
        # Convert message to upper-case for string compare later
        in_str = in_str.upper()
        # Only messages starting with FE are valid
        if in_str[:2] != 'FE':
            raise Exception('Data corrupt')
        # Strip CRC and FE header
        data_check = in_str[2:][:-2]
        # Assemble CRC in message
        crc_to_check = ''.join(('0X', in_str[-2:]))
        # Calculate CRC For message
        crc_calc = str(self.__crc(data_check)).upper()
        # Return compare
        return crc_calc == crc_to_check

    def __send_cmd(self, cmd):
        '''
        Send cmd
        '''
        # All commands are prefixed with 0xFE
        prefix_cmd = 'FE'
        # Length of message is total length / 2 minus cmd (2 bytes) (and strip '0x')
        cmdlen = hex(int(len(cmd) / 2) - 2)[2:]
        # Pad length to 2 bytes
        if len(cmdlen) == 1:
            cmdlen = ''.join(('0', str(cmdlen)))
        # Assemble and add CRC
        cmd = ''.join((prefix_cmd, cmdlen, cmd, self.__crc(cmdlen+cmd)[2:]))
        # Send each set of two characters as byte
        for i in range(0, len(cmd), 2):
            new_char = int(cmd[i:i+2], 16).to_bytes(1, 'big')
            self.writer.write(new_char)

    def __listen(self, timeout=1000):
        '''
        Listen for serial output
        When serial buffer is empty after timeout, return ''

        When reader has no in_waiting function assume read() is non-blocking.
        TODO: Convert str to bytearray
        '''
        out_str = ""
        # micropython has no float for time...
        end_time_ms = (time.time_ns() // 1000000) + timeout
        if self.system_type == 'python3-serial':
            while (self.reader.in_waiting == 0) and ((time.time() * 1000) < end_time_ms):
                time.sleep(0.01)
            time.sleep(0.1)
            # Only read characters when serial buffer is not empty
            while self.reader.in_waiting > 0:
                new_char = self.reader.read()
                hex_char = new_char.hex()
                if len(hex_char) == 1:
                    hex_char = '0'+hex_char
                out_str += hex_char
        else:
            # micropython seems to be slow;
            time.sleep(0.5)
            # Read current buffer
            buffer = self.reader.read()
            # While buffer is empty, retry until buffer is not, or timeout expires
            while (buffer is None) and ((time.time_ns() // 1000000) < end_time_ms):
                time.sleep(0.1)
                buffer = self.reader.read()
            # After first characters are received, wait short time and read the rest.
            time.sleep(0.2)
            temp_str = b""
            while buffer is not None:
                temp_str += buffer
                time.sleep(0.1)
                buffer = self.reader.read()
            # Convert binary string to hex-string
            for i in temp_str:
                temp_char = hex(i)[2:]
                if len(temp_char) == 1:
                    temp_char = '0'+temp_char
                out_str += temp_char
        return out_str

    def __decode(self, in_str, inverter_index):
        '''
        Decode message type, start decoding of received information
        Called by: parse
        '''
        known_cmds = {
            '2101': 'ZigbeePing',
            '2400': 'AF_REGISTER',
            '2401': 'AF_DATA_REQ',
            '2600': 'ZB_START_REQUEST',
            '2605': 'ZB_WRITE_CONFIGURATION',
            '2700': 'StartCoordinator',
            '4081': 'StartupRadio',
            '4100': 'SYS_RESET_REQ',
            '4180': 'SYS_RESET_INT',
            '4481': 'AF_INCOMING_MSG',
            '6101': 'ZigbeePingResp',
            '6400': 'AF_REG_Resp',
            '6401': 'AF_DATA_REQ_Resp',
            '6605': 'ZB_WR_CONF_Resp',
            '6700': 'StartCoordinatorResp'}

        # Replace code with string when available
        cmd_code = in_str[4:8]
        if cmd_code in known_cmds:
            cmd_code = known_cmds.get(cmd_code)

        data = in_str[8:-2]

        # Check CRC
        crc = self.__crc_check(in_str)

        if cmd_code == 'AF_INCOMING_MSG' and crc:
            # Can be answer to poll request or pair request
            pair = False
            if len(in_str) < 222:
                for inverter in self.inv_data:
                    if inverter['serial'] in in_str:
                        # Decode pair request is done in pair_inverter function
                        data = in_str
                        pair = True
                        break
            else:
                if not pair and (inverter_index >= 0):
                    # Decode inverter poll response
                    data = self.__decode_inverter_values(in_str, inverter_index)
        return {'cmd': cmd_code, 'crc': crc, 'data': data}

    def __decode_inverter_values(self, in_str, inverter_index):
        '''
        Transform byte string of poll response to values
        called by: __decode
        '''
        # We do not need the first 38 bytes apparently
        data = in_str[38:]
        voltdc = []
        currdc = []
        en_pan = []
        num_panels = self.inv_data[inverter_index]['panels']
        invtemp = -258.7 + (int(data[24:28], 16) * 0.2752) # Inverter temperature
        freq_ac = 50000000 / int(data[28:34], 16) # AC Fequency
        # DC Current for panel 1
        currdc.append((int(data[48:50], 16) + (int(data[51], 16) * 256)) * (27.5 / 4096))
        # DC Volts for panel 1
        voltdc.append((int(data[52:54], 16) * 16 + int(data[50], 16)) * (82.5 / 4096))
        currdc.append((int(data[54:56], 16) + (int(data[57], 16) * 256)) * (27.5 / 4096))
        voltdc.append((int(data[58:60], 16) * 16 + int(data[56], 16)) * (82.5 / 4096))
        volt_ac = (int(data[60:64], 16) * (1 / 1.3277)) / 4
        # Energy counter (daily reset), swapped panel 1 and 2 as reported in
        # https://github.com/No13/ApsYc600-Pythonlib/issues/1
        en_pan.append(int(data[88:94], 16) * (8.311 / 3600))
        en_pan.append(int(data[78:84], 16) * (8.311 / 3600))
        if num_panels == 4:
            currdc.append((int(data[34:36], 16) + (int(data[37], 16) * 256)) *(27.5 / 4096))
            voltdc.append((int(data[38:40], 16) * 16 + int(data[36], 16)) * (82.5 / 4096))
            currdc.append((int(data[28:30], 16) + (int(data[31], 16) * 256)) *(27.5 / 4096))
            voltdc.append((int(data[32:34], 16) * 16 + int(data[30], 16)) * (82.5 / 4096))
            en_pan.append(int(data[98:104], 16) * (8.311 / 3600))
            en_pan.append(int(data[108:114], 16) * (8.311 / 3600))
            return {
                'temperature': round(invtemp, 2),
                'freq_ac': round(freq_ac, 2),
                'current_dc1': round(currdc[0], 2),
                'current_dc2': round(currdc[1], 2),
                'current_dc3': round(currdc[2], 2),
                'current_dc4': round(currdc[3], 2),
                'voltage_dc1': round(voltdc[0], 2),
                'voltage_dc2': round(voltdc[1], 2),
                'voltage_dc3': round(voltdc[2], 2),
                'voltage_dc4': round(voltdc[3], 2),
                'voltage_ac': round(volt_ac, 2),
                'energy_panel1': round(en_pan[0], 3),
                'energy_panel2': round(en_pan[1], 3),
                'energy_panel3': round(en_pan[2], 3),
                'energy_panel4': round(en_pan[3], 3),
                'watt_panel1': round(currdc[0] * voltdc[0], 2),
                'watt_panel2': round(currdc[1] * voltdc[1], 2),
                'watt_panel3': round(currdc[2] * voltdc[2], 2),
                'watt_panel4': round(currdc[3] * voltdc[3], 2)}

        return {
            'temperature': round(invtemp, 2),
            'freq_ac': round(freq_ac, 2),
            'current_dc1': round(currdc[0], 2),
            'current_dc2': round(currdc[1], 2),
            'voltage_dc1': round(voltdc[0], 2),
            'voltage_dc2': round(voltdc[1], 2),
            'voltage_ac': round(volt_ac, 2),
            'energy_panel1': round(en_pan[0], 3),
            'energy_panel2': round(en_pan[1], 3),
            'watt_panel1': round(currdc[0] * voltdc[0], 2),
            'watt_panel2': round(currdc[1] * voltdc[1], 2)}

    def __parse(self, in_str, inverter_index=-1):
        '''
        Parse incoming messages
            Split multiple messages, decode them and return the output
        '''
        in_str = in_str.upper()
        decoded_cmd = []
        while in_str[:2] == 'FE':
            # New command found
            str_len = int(in_str[2:4], 16) # Decode cmd len
            min_len = int((len(in_str) - 10) / 2) # FE XX XXXX ... XX
            if str_len > min_len: # Check if data is sufficient for found str_len
                raise Exception('Data corrupt, length field does not match actual length')
            cmd = in_str[:(10 + str_len * 2)] # Copy command to str
            in_str = in_str[10 + (str_len * 2):]
            decoded_cmd.append(self.__decode(cmd, inverter_index))
        return decoded_cmd

    # Public functions

    def add_inverter(self, inv_serial, inv_id, num_panels):
        '''
        Add inverter to struct,
            inv_id is required for polling
            serial is required for pairing
            num_panels is required to determine inverter type (YC600 / QS1)
        '''
        if num_panels not in (2, 4):
            raise Exception("Only 2 or 4 panels supported")
        inverter = {
            'serial': inv_serial,
            'inv_id': inv_id,
            'panels': num_panels}
        self.inv_data.append(inverter)
        inverter_index = len(self.inv_data) -1
        if num_panels == 2:
            self.energy_data.append(
                {
                    'last_energy_p1': 0,
                    'last_energy_p2': 0,
                    'energy_offset_p1': 0,
                    'energy_offset_p2': 0})
        else:
            self.energy_data.append(
                {
                    'last_energy_p1': 0,
                    'last_energy_p2': 0,
                    'last_energy_p3': 0,
                    'last_energy_p4': 0,
                    'energy_offset_p1': 0,
                    'energy_offset_p2': 0,
                    'energy_offset_p3': 0,
                    'energy_offset_p4': 0})
        return inverter_index # Return index for last inverter

    def set_inverter_id(self, inv_index, inv_id):
        '''
        Set inverter ID for existing inverter
        '''
        if len(self.inv_data) <= inv_index:
            raise Exception('Invalid inverter index')
        self.inv_data[inv_index]['inv_id'] = inv_id
        return True

    def reset_counters(self, inverter_index):
        '''
        Reset historical data
        '''
        self.energy_data[inverter_index] = {
            'last_energy_p1': 0,
            'last_energy_p2': 0,
            'energy_offset_p1': 0,
            'energy_offset_p2': 0}

    def poll_inverter(self, inverter_index):
        '''
        Get values from inverter.

        Uses previous values to determine inverter restarts.
        In case of inverter restart the energy counters will continue (using offset)
        instead of restarting from 0.

        This will require you to reset_counters every day to begin a new day at 0.
        '''
        # Clear serial buffer
        self.clear_buffer()
        if inverter_index > len(self.inv_data) -1:
            raise Exception('Invalid inverter')
        num_panels = self.inv_data[inverter_index]['panels']
        # Send poll request
        self.__send_cmd(''.join(
            ('2401', self.__reverse_byte_str(self.inv_data[inverter_index]['inv_id']),
             '1414060001000F13', self.__reverse_byte_str(self.controller_id),
             'FBFB06BB000000000000C1FEFE')))
        time.sleep(1)
        # Check poll response
        return_str = self.__listen()
        response_data = self.__parse(return_str, inverter_index)
        # Check if correct response is found...
        for response in response_data:
            if response['cmd'] == '4480' and 'CD' in response['data']:
                return {'error': 'NoRoute'}
            if response['cmd'] == 'AF_INCOMING_MSG':
                # Calculate energy
                if not 'data' in response:
                    return {'error': 'incomplete'}
                if not 'energy_panel1' in response['data']:
                    return {'error': 'incomplete', 'data': response}
                if response['data']['voltage_dc1'] + response['data']['voltage_dc2'] < 0.1:
                    return {'error': 'data error', 'data': response}
                # Retrieve last energy values
                last_energy = self.energy_data[inverter_index]['last_energy_p1']
                last_energy += self.energy_data[inverter_index]['last_energy_p2']
                # Retrieve current energy values
                curr_energy = response['data']['energy_panel1']
                curr_energy += response['data']['energy_panel2']
                # Retrieve offset energy
                offset_energy = self.energy_data[inverter_index]['energy_offset_p1']
                offset_energy += self.energy_data[inverter_index]['energy_offset_p2']
                if num_panels == 4:
                    last_energy += self.energy_data[inverter_index]['last_energy_p3']
                    last_energy += self.energy_data[inverter_index]['last_energy_p4']
                    curr_energy += response['data']['energy_panel3']
                    curr_energy += response['data']['energy_panel4']
                    offset_energy += self.energy_data[inverter_index]['energy_offset_p3']
                    offset_energy += self.energy_data[inverter_index]['energy_offset_p4']
                # If offset + current becomes smaller than last value then update offsets
                if (curr_energy + offset_energy) < last_energy:
                    # Reset of inverter: update offset
                    new_offset = self.energy_data[inverter_index]['last_energy_p1']
                    self.energy_data[inverter_index]['energy_offset_p1'] = new_offset
                    new_offset = self.energy_data[inverter_index]['last_energy_p2']
                    self.energy_data[inverter_index]['energy_offset_p2'] = new_offset
                    if num_panels == 4:
                        new_offset = self.energy_data[inverter_index]['last_energy_p3']
                        self.energy_data[inverter_index]['energy_offset_p3'] = new_offset
                        new_offset = self.energy_data[inverter_index]['last_energy_p4']
                        self.energy_data[inverter_index]['energy_offset_p4'] = new_offset
                # Return offset + current value & update last value
                new_energy = self.energy_data[
                    inverter_index]['energy_offset_p1'] + response['data']['energy_panel1']
                self.energy_data[
                    inverter_index]['last_energy_p1'] = new_energy
                response['data']['energy_panel1'] = new_energy

                new_energy = self.energy_data[
                    inverter_index]['energy_offset_p2'] + response['data']['energy_panel2']
                self.energy_data[
                    inverter_index]['last_energy_p2'] = new_energy
                response['data']['energy_panel2'] = new_energy

                if num_panels == 4:
                    new_energy = self.energy_data[
                        inverter_index]['energy_offset_p3'] + response['data']['energy_panel3']
                    self.energy_data[
                        inverter_index]['last_energy_p3'] = new_energy
                    response['data']['energy_panel3'] = new_energy

                    new_energy = self.energy_data[
                        inverter_index]['energy_offset_p4'] + response['data']['energy_panel4']
                    self.energy_data[
                        inverter_index]['last_energy_p4'] = new_energy
                    response['data']['energy_panel4'] = new_energy

                return response
        return {'error': 'timeout', 'data': response_data}

    def ping_radio(self):
        '''
        Check if radio module is ok
        '''
        self.__send_cmd('2101')
        str_resp = self.__listen()
        if str_resp is None:
            print("Ping reply empty")
            return False
        cmd_output = self.__parse(str_resp)

        for cmd in cmd_output:
            if cmd['cmd'] == 'ZigbeePingResp' and cmd['crc'] and cmd['data'] == '7907':
                return True
        print("Ping failed", cmd_output)
        return False

    def start_coordinator(self, pair_mode=False):
        '''
        Start coordinator proces in Zigbee radio.
        Resets modem
        '''
        rev_controll_id = self.__reverse_byte_str(self.controller_id)
        init_cmd = []
        expect_response = []
        init_cmd.append('2605030103') # 20 ms
        expect_response.append(['fe0166050062'])
        init_cmd.append('410000') # 500 ms
        expect_response.append(['fe064180020202020702c2'])
        init_cmd.append('26050108FFFF'+rev_controll_id) # 15 ms
        expect_response.append(['fe0166050062'])
        init_cmd.append('2605870100') # 10 ms
        expect_response.append(['fe0166050062'])
        init_cmd.append('26058302'+self.controller_id[:4]) # 20 ms
        expect_response.append(['fe0166050062'])
        init_cmd.append('2605840400000100') # 20 ms
        expect_response.append(['fe0166050062'])
        init_cmd.append('240014050F00010100020000150000') # 10 ms
        expect_response.append(['fe0164000065'])
        init_cmd.append('2600') # 1000 ms
        expect_response.append(['fe00660066', 'fe0145c0088c']) # second is optional
        init_cmd.append('6700')
        expect_response.append(['fe0e670000ffff'])

        if not pair_mode:
            init_cmd.append(''.join(
                ('2401FFFF1414060001000F1E', rev_controll_id, 'FBFB11',
                 '00000D6030FBD3000000000000000004010281FEFE'))) # 20 ms
            expect_response.append(
                ['fe0164010064',
                 'fe0145c0088c',
                 'fe0145c0088c',
                 'fe0145c0098d'])

        all_verified = True
        for cmd in init_cmd:
            self.__send_cmd(cmd)
            result_str = self.__listen(1100)
            cmd_index = init_cmd.index(cmd)
            try:
                if not expect_response[cmd_index][0] in result_str:
                    all_verified = False
                    print('Verify failed', cmd, result_str)
            finally:
                pass
            # Final commands need more time to process
            if init_cmd.index(cmd) > 6:
                time.sleep(1.5)
        return all_verified

    def check_coordinator(self):
        '''
        Send 2700 message to modem, show response
        Result should contain 0709 (??)
        '''
        self.clear_buffer()
        self.__send_cmd('2700')
        print('check_coord', self.__listen(500))

    def clear_buffer(self):
        '''
        Return serial buffer after waiting 100 msec
        '''
        return self.__listen(100)

    def pair_inverter(self, inverter_index):
        '''
        Pair with inverter at index inv_index
        '''
        if inverter_index > len(self.inv_data) -1:
            raise Exception('Invalid inverter')
        self.start_coordinator(True)
        init_cmd = []
        inverter_serial = self.inv_data[inverter_index]['serial']
        pair_cmd = ''.join(
            ("24020FFFFFFFFFFFFFFFFF14FFFF140D0200000F1100",
             inverter_serial, "FFFF10FFFF",
             self.__reverse_byte_str(self.controller_id)))
        init_cmd.append(pair_cmd)
        pair_cmd = ''.join(
            ("24020FFFFFFFFFFFFFFFFF14FFFF140C0201000F0600",
             inverter_serial))
        init_cmd.append(pair_cmd)
        pair_cmd = ''.join(
            ("24020FFFFFFFFFFFFFFFFF14FFFF140F0102000F1100",
             inverter_serial,
             self.__reverse_byte_str(self.controller_id)[-4:],
             "10FFFF", self.__reverse_byte_str(self.controller_id)))
        init_cmd.append(pair_cmd)
        pair_cmd = ''.join(
            ("24020FFFFFFFFFFFFFFFFF14FFFF14010103000F0600",
             self.__reverse_byte_str(self.controller_id)))
        init_cmd.append(pair_cmd)

        found = False
        for cmd in init_cmd:
            self.__send_cmd(cmd)
            result_str = self.__listen(1100)
            # no check in place to verify responses from pair commands
            time.sleep(1.5)
            result = self.__parse(result_str)

            for result_obj in result:
                if inverter_serial in result_obj['data']:
                    inv_id_start = 12 + result_obj['data'].index(inverter_serial)
                    inv_id = result_obj['data'][inv_id_start:inv_id_start+4]
                    if inv_id not in (
                            '0000', 'FFFF',
                            self.__reverse_byte_str(self.controller_id)[-4:]):

                        found = inv_id[2:]+inv_id[:2]
                        print('Inverter ID Found', found)
                        return found

        return found
