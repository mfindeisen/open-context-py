import re
import datetime
import hashlib
from unidecode import unidecode
from dateutil.parser import parse
from django.conf import settings


class DescriptionDataType():
    """ 
    classifies a description field by data_type according to its values

    """

    def __init__(self):
        self.id = None
        self.label = None
        self.data_type = None
        self.total_count = 0
        self.datetime_count = 0
        self.int_count = 0
        self.float_count = 0
        self.boolean_count = 0
        self.uniqe_str_hashes = []
        self.earliest_date = '1950-01-01'
    
    def classify_data_type(self):
        data_type = None
        num_unique = len(self.uniqe_str_hashes)
        """ classifies the data type based on current guesses """
        if self.datetime_count > (10 * self.int_count) \
           and self.datetime_count > (10 * self.float_count) \
           and self.datetime_count >= .9 * self.total_count:
            data_type = 'xsd:date'
        if data_type is None:
            if self.boolean_count >= .9 * self.total_count \
               and num_unique <= 4 \
               and self.total_count >= 20:
                data_type = 'xsd:boolean'
        if data_type is None:
            if self.float_count >= .9 * self.total_count:
                if self.int_count >= .95 * self.total_count:
                    data_type = 'xsd:integer'
                else:
                    data_type = 'xsd:double'
        if data_type is None:
            if num_unique <= 50 and (num_unique * 4 <= self.total_count):
                data_type = 'id'
            else:
                data_type = 'xsd:string'
        return data_type
    
    def check_record_datatype(self, record):
        """ checks the record for conformance to 1 or more
            data_types. It adds to the count for records that
            conform to a given data type, because sometimes
            a single record is valid as more than 1 data type
        """
        record = str(record)
        record = record.strip()
        if len(record) > 0:
            # note we're checking a value
            self.total_count += 1
            # check if valid as a Boolean
            boolean_literal = self.validate_convert_boolean(record)
            if boolean_literal is not None:
                self.boolean_count += 1
            # check if valid as an Integer
            int_literal = self.validate_integer(record)
            if int_literal is not None:
                self.int_count += 1
            # check if valid as an Float
            d_literal = self.validate_numeric(record)
            if d_literal is not None:
                self.float_count += 1
            # check if valid as a datetime
            date_obj = self.validate_datetime(record)
            if date_obj is not None:
                self.datetime_count += 1
            # now make a hash of the record, add if unique
            hash_val = self.make_hash(record)
            if hash_val not in self.uniqe_str_hashes:
                self.uniqe_str_hashes.append(hash_val)
        
    def make_hash(self, record):
        """
        creates a of a record
        """
        hash_obj = hashlib.sha1()
        rec_str = str(record)
        hash_obj.update(rec_str.encode('utf-8'))
        return hash_obj.hexdigest()    
        
    def validate_datetime(self, record):
        """validates as a datetime. returns a date_obj
           if valid, none if not
        """
        date_obj = None
        try:
            record = str(record)
            date_obj = parse(record)
        except:
            date_obj = None
        if date_obj is not None:
           early_obj = parse(self.earliest_date)
           early_obj = early_obj.replace(tzinfo=None)
           now_obj = datetime.datetime.now()
           now_obj = now_obj.replace(tzinfo=None)
           check_obj = date_obj.replace(tzinfo=None)
           if check_obj > now_obj or check_obj < early_obj:
                date_obj = None
                # print('Date object seems not realistic !')
        return date_obj
    
    def validate_integer(self, record):
        """ validates a string to be an integer
            returns None if not
        """
        output = None
        float_record = self.validate_numeric(record)
        if float_record is not None:
            if round(float_record, 0) == float_record:
                try:
                    output = int(float_record)
                except ValueError:
                    output = None
        return output

    def validate_numeric(self, record):
        """ validates a string to be a number
            returns None if not
        """
        try:
            output = float(record)
        except ValueError:
            output = None
        return output

    def validate_convert_boolean(self, record):
        """ Validates boolean values for a record
            returns a boolean 0 or 1 if
        """
        output = None
        record = str(record)
        record = record.lower()
        booleans = {'n': 0,
                    'no': 0,
                    'none': 0,
                    'absent': 0,
                    'false': 0,
                    'f': 0,
                    '0': 0,
                    '0.0': 0,
                    'y': 1,
                    'yes': 1,
                    'present': 1,
                    'true': 1,
                    't': 1,
                    '1': 1,
                    '1.0': 1}
        if record in booleans:
            output = booleans[record]
        return output
