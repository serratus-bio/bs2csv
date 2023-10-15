# bs2csv

## Description
Python script to extract metadata for a list of given BioSample ids from the NCBI BioSample database. Data is extracted from XML files and output to a CSV.

> [!NOTE]
> CSV output works best when comparing metadata from different BioSamples in the same BioProject as the tag names in the XML will be consistent. Comparing runs from different BioProjects can result in a messy CSV output.  

## Local Usage
### Setup

```sh
# [optional] create/load virtualenv
pip install -r requirements.txt
```

### Example usage

```sh
python bs2csv.py input_ids.txt 
```
- `input_ids.txt` is a text file containing new line separated NCBI BioSample accession ids

### Example usage with flags

```sh
python bs2csv.py input_ids.txt  -o metadata_output.csv -v values.txt
```
- `metadata_output.csv` is the name of the desired output file. Defaults to `biosample_metadata.csv`
- `values.txt` is a text file containing new line separated values that are used when extracting metadata
  -  only the information from tags found in `values.txt` will be stored in the output

