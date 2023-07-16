import xml.sax
import xmltodict
import argparse
import csv
import requests

class BioSamplesParser(xml.sax.ContentHandler):
    '''
    SAX parser to extract information from BioSamples XML file and store it in a dictionary.
    '''
    def __init__(self, content_dict) -> None:
        super().__init__()
        self.cur_dict = content_dict
        self.biosample_id = ''

        self.is_db = False
        self.cur_db = ''
        self.is_title = False
        self.paragraph_string = ''
        self.is_paragraph = False
        self.is_owner = False
        self.is_package = False
        self.attribute_name = ''
        self.is_link = False
        self.link_name = ''
        self.owner_xml_string = '<Owner>'

    def unpack_owner_dict(self, xml_dict: dict, parent_key: str = '', output_list: list = None) -> list:
            '''
            Unpack a given owner dictionary into a single list that has all values from the dictionary.
            The list contains tuples of the form (key, value).
            If the dictionary has #text as a key, store the other attributes in the key as well.
            '''
            if output_list is None:
                output_list = []
            for k, v in xml_dict.items():
                key = parent_key + '/' + k
                if type(v) == dict:
                    self.unpack_owner_dict(v, key, output_list)
                elif type(v) == list and len(v) > 0 and type(v[0]) == dict:
                    key_copy = key
                    for item in v:
                        if '#text' in item.keys():
                            key = key_copy
                            for k2, v2 in item.items():
                                if k2 != '#text':
                                    key = key + '/' + k2 + '=' + v2
                            output_list.append((key, item['#text'])) 
                        else:
                            self.unpack_owner_dict(item, key, output_list)
                else:
                    output_list.append((key, v))

            return output_list

    def startElement(self, name, attrs):
        if name == 'BioSample':
            self.biosample_id == attrs['accession']
            self.cur_dict['submission_date'] = attrs['submission_date'] if 'submission_date' in attrs else ''
            self.cur_dict['last_update'] = attrs['last_update'] if 'last_update' in attrs else ''
            self.cur_dict['publication_date'] = attrs['publication_date'] if 'publication_date' in attrs else ''
            self.cur_dict['access'] = attrs['access'] if 'access' in attrs else ''
        elif name == 'Id':
            self.is_db = True
            try:
                self.cur_db = attrs['db']
            except KeyError:
                self.cur_db = attrs['db_label']
        elif name == 'Title':
            self.is_title = True
        elif name == 'Organism':
            self.cur_dict['organism_taxonomy_id'] = attrs['taxonomy_id']
            self.cur_dict['organism_taxonomy_name'] = attrs['taxonomy_name']
        elif name == 'Paragraph':
            self.is_paragraph = True
        elif name == 'Owner':
            self.is_owner = True
        elif self.is_owner:
            self.owner_xml_string += '<{}'.format(name)
            if len(attrs) > 0:
                for attr in attrs.getNames():
                    self.owner_xml_string += ' {}="{}"'.format(attr, attrs[attr])
            self.owner_xml_string += '>'
        elif name == 'Package':
            self.is_package = True
        elif name == 'Attribute':
            try:
                self.attribute_name = attrs['harmonized_name']
            except KeyError:
                self.attribute_name = attrs['attribute_name']
        elif name == 'Link':
            # assumes format for <Link> tag has either url or entrez attribute
            if 'type' in attrs and attrs['type'] == 'url' and 'label' in attrs:
                # doesn't work well for GEO sample labels
                self.link_name = attrs['label']
            elif 'type' in attrs and attrs['type'] == 'entrez':
                self.link_name = attrs['target']
            self.is_link = True
        elif name == 'Status':
            self.cur_dict['status'] = attrs['status']
            self.cur_dict['when'] = attrs['when']

    def characters(self, content):
        if self.is_title:
            self.cur_dict['title'] = content
            self.is_title = False
        elif self.is_db:
            self.cur_dict[self.cur_db + '_db'] = content
            self.is_db = False
        elif self.is_paragraph:
            self.paragraph_string += content
            self.is_paragraph = False
        elif self.is_owner:
            self.owner_xml_string += content
        elif self.is_package:
            self.cur_dict['package'] = content
            self.is_package = False
        elif self.attribute_name:
            self.cur_dict[self.attribute_name] = content
            self.attribute_name = ''
        elif self.is_link:
            self.cur_dict[self.link_name] = content
            self.link_name = ''
            self.is_link = False

    def endElement(self, name):
        if name == 'Owner':
            self.owner_xml_string += '</Owner>'
            # replace ampersand with 'and' to avoid xml parsing error
            self.owner_xml_string = self.owner_xml_string.replace('&', 'and')
            owner_dict = self.unpack_owner_dict(xml_dict=xmltodict.parse(self.owner_xml_string))
            for k, v in owner_dict:
                self.cur_dict[k[7:]] = v
            self.is_owner = False
        elif self.is_owner:
            self.owner_xml_string += '</{}>'.format(name)
        if name == 'BioSample':
            self.cur_dict['paragraph'] = self.paragraph_string
            self.paragraph_string = ''      


    def endDocument(self):
        pass



arg_parser = argparse.ArgumentParser(description="""Read in a list of biosample ids and output a csv file with the biosample metadata. Metadata is extracted from biosamples xml files from NCBI.

Example usage:
    python bs2csv.py biosample_ids.txt -o metadata.csv
    """, formatter_class=argparse.RawTextHelpFormatter)
arg_parser.add_argument('input_file', help='Input text file with a different biosample id on each line')
arg_parser.add_argument('-o', help='Name for output csv file with biosample metadata. Defaults to "biosample_metadata.csv"', default='biosample_metadata.csv', dest='output_file', metavar='output_file.csv')

args = arg_parser.parse_args()
input_file = args.input_file
output_file = args.output_file

with open(input_file, 'r') as f:
    # results_dict contains a dictionary for each biosample id with the metadata
    results_dict = {}
    biosample_ids = f.read().splitlines()
    for accession in biosample_ids:
        # content_dict contains the metadata for a single biosample id
        content_dict = {}
        handler = BioSamplesParser(content_dict)
        url = 'https://serratus-biosamples.s3.us-east-1.amazonaws.com/biosamples_split/' + accession + '.xml'
        headers = {'Host': 'serratus-biosamples.s3.amazonaws.com'}
        # get the xml file from the serratous-biosamples s3 bucket
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print('Error: status code {} for {}'.format(response.status_code, accession))
            continue
        result_string = response.text
        # parse the response stirng with xml.sax
        try:
            xml.sax.parseString(result_string, handler)
        except xml.sax.SAXParseException:
            print('Error: SAXParseException for {}'.format(accession))
            continue
        # store the metadata for the biosample id in results_dict
        results_dict[accession] = content_dict

# ensure that all headers are stored in csv_headers
csv_headers = ['biosample_id']
for _, data_dict in results_dict.items():
    for header, _ in data_dict.items():
        if header not in csv_headers:
            csv_headers.append(header)

# write results to csv file
with open(output_file, 'w', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(csv_headers)
    for accession, data_dict in results_dict.items():
        row = [accession]
        for header in csv_headers[1:]:
            if header in data_dict:
                row.append(data_dict[header])
            else:
                row.append('')
        writer.writerow(row)
