### Setting the environment
import pandas as pd
import os
import datetime as dt
import regex as re
import json


def merge_data():
    ### Loading data

    ### From ckan output
    source_ckan = pd.DataFrame()
    folder = "data/ckan/"
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit(".", 1)[1] == "csv":
                print(filename)
                source_ckan = pd.concat(
                    [
                        source_ckan,
                        pd.read_csv(
                            folder + r"/" + filename, parse_dates=["DateCreated","DateUpdated"], lineterminator='\n'
                        ),
                    ]
                )
    source_ckan["Source"] = "ckan API"

    ### From scotgov csv
    source_scotgov = pd.read_csv("data/scotgov-datasets-sparkql.csv")
    source_scotgov = source_scotgov.rename(
        columns={
            "title": "Title",
            "category": "OriginalTags",
            "organization": "Owner",
            "notes": "Description",
            "date_created": "DateCreated",
            "date_updated": "DateUpdated",
            "url": "PageURL",
            "licence":"License"
        }
    )
    source_scotgov["Source"] = "sparql"
    source_scotgov['DateUpdated'] = pd.to_datetime(source_scotgov['DateUpdated'], utc=True).dt.tz_localize(None)
    source_scotgov['DateCreated'] = pd.to_datetime(source_scotgov['DateCreated'], utc=True).dt.tz_localize(None)

    ### From arcgis api
    source_arcgis = pd.DataFrame()
    folder = "data/arcgis/"
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit(".", 1)[1] == "csv":
                source_arcgis = pd.concat(
                    [
                        source_arcgis,
                        pd.read_csv(
                            folder + r"/" + filename, parse_dates=["DateCreated","DateUpdated"]
                        ),
                    ]
                )
    source_arcgis["Source"] = "arcgis API"

    ### From usmart api
    source_usmart = pd.DataFrame()
    folder = "data/USMART/"
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit(".", 1)[1] == "csv":
                source_usmart = pd.concat(
                    [
                        source_usmart,
                        pd.read_csv(
                            folder + r"/" + filename, parse_dates=["DateCreated","DateUpdated"]
                        ),
                    ]
                )
    source_usmart["Source"] = "USMART API"
    source_usmart["DateUpdated"] = source_usmart["DateUpdated"].dt.tz_localize(None)
    source_usmart["DateCreated"] = source_usmart["DateCreated"].dt.tz_localize(None)

    ## From DCAT
    source_dcat = pd.DataFrame()
    folder = "data/dcat/"
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit(".", 1)[1] == "csv":
                source_dcat = pd.concat(
                    [
                        source_dcat,
                        pd.read_csv(
                            folder + r"/" + filename, parse_dates=["DateCreated","DateUpdated"]
                        ),
                    ]
                )
    source_dcat["DateUpdated"] =  source_dcat["DateUpdated"].dt.tz_localize(None)
    #source_dcat["DateCreated"] = source_dcat["DateCreated"].dt.tz_localize(None) ### DateCreated currently not picked up in dcat so all are NULL
    source_dcat["Source"] = "DCAT feed"

    ## From web scraped results
    source_scraped = pd.DataFrame()
    folder = "data/scraped-results/"
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit(".", 1)[1] == "csv":
                source_scraped = pd.concat(
                    [
                        source_scraped,
                        pd.read_csv(
                            folder + r"/" + filename, parse_dates=["DateCreated","DateUpdated"]
                        ),
                    ]
                )
    source_scraped["Source"] = "Web Scraped"

    ### Combine all data into single table
    data = pd.concat(
        [
            source_ckan,
            source_arcgis,
            source_usmart,
            source_scotgov,
            source_dcat,
            source_scraped,
        ]
    )
    data = data.reset_index(drop=True)

    ### Saves copy of data without cleaning - for analysis purposes
    data.to_csv("data/merged_output_untidy.csv", index=False)

    ### clean data
    data = clean_data(data)

    ### Output cleaned data to csv
    data.to_csv("data/merged_output.csv", index=False)

    return data


def clean_data(dataframe):
    """cleans data in a dataframe

    Args:
        dataframe (pd.dataframe): the name of the dataframe of data to clean

    Returns:
        dataframe: dataframe of cleaned data
    """
    ### to avoid confusion and avoid re-naming everything...
    data = dataframe

    ### Renaming entries to match
    owner_renames = {
        "Aberdeen": "Aberdeen City Council",
        "Dundee": "Dundee City Council",
        "Perth": "Perth and Kinross Council",
        "Stirling": "Stirling Council",
        "Angus": "Angus Council",
        "open.data@southayrshire": "South Ayrshire Council",
        "SEPA": "Scottish Environment Protection Agency",
        "South Ayrshire": "South Ayrshire Council",
        "East Ayrshire": "East Ayrshire Council",
        "Highland Council GIS Organisation": "Highland Council",
        "Scottish.Forestry": "Scottish Forestry",
        "Na h-Eileanan an Iar": "Comhairle nan Eilean Siar",
    }
    data["Owner"] = data["Owner"].replace(owner_renames)
    ### Format dates as datetime type
    data["DateCreated"] = pd.to_datetime(
        data["DateCreated"], format="%Y-%m-%d", errors="coerce", utc=True
    ).dt.date
    data["DateUpdated"] = pd.to_datetime(
        data["DateUpdated"], format="%Y-%m-%d", errors="coerce", utc=True
    ).dt.date
    ### Inconsistencies in casing for FileType
    data["FileType"] = data["FileType"].str.upper()
    ### Creating a dummy column
    data["AssetStatus"] = None

    ### Cleaning dataset categories
    def tidy_categories(categories_string):
        """tidies the categories: removes commas, strips whitespace, converts all to lower and strips any trailing ";"

        Args:
            categories_string (string): the dataset categories as a string
        """
        tidied_string = str(categories_string).replace(",", ";")
        tidied_list = [
            cat.lower().strip() for cat in tidied_string.split(";") if cat != ""
        ]
        tidied_string = ";".join(str(cat) for cat in tidied_list if str(cat) != "nan")
        if len(tidied_string) > 0:
            if tidied_string[-1] == ";":
                tidied_string = tidied_string[:-1]
        return tidied_string

    ### Tidy tag columns
    data["OriginalTags"] = data["OriginalTags"].apply(tidy_categories)
    data["ManualTags"] = data["ManualTags"].apply(tidy_categories)

    ### Creating dataset categories for ODS
    def find_keyword(str_tofind, str_findin):
        """Finds if single word or phrase exists in string

        Args:
            str_tofind (str): the word or phrase to find
            str_findin (str): the body of text to search in

        Returns:
            boolean: True if match is found
        """
        if re.search(r"\b" + re.escape(str_tofind) + r"\b", str_findin, re.I):
            return True
        return False

    def match_categories(str_tocategorise):
        """Cycles through keywords and keyphrases to check if used in body of text

        Args:
            str_tocategorise (str): body of text to search in

        Returns:
            list: the resulting categories as a string, as well as a dictionary of the keyphrases which resulted in a category
        """
        category_dict = {}
        for category in ods_categories.keys():
            keyword_list = []
            for keyword in ods_categories[category]:
                if find_keyword(keyword, str_tocategorise):
                    keyword_list.append(keyword)
                    category_dict[category] = keyword_list
        if len(category_dict) == 0:
            category_list = "Uncategorised"
        else:
            category_list = ";".join(list(category_dict.keys()))
        return [category_list, category_dict]

    def get_categories(row_index):
        """combines title and description together to then search for keyword or keyphrase in

        Args:
            row_index (pandas df row): a single row in a pandas dataframe to check. Must have columns "Title" and "Description"

        Returns:
            list: the resulting categories as a string, as well as a dictionary of the keyphrases which resulted in a category
        """
        str_title_description = (
            str(row_index["Title"]) + " " + str(row_index["Description"])
        )
        categories_result = match_categories(str_title_description)
        return categories_result

    with open("ODSCategories.json") as json_file:
        ods_categories = json.load(json_file)

    ### Apply ODS categorisation
    data[["ODSCategories", "ODSCategories_Keywords"]] = data.apply(
        lambda x: get_categories(x), result_type="expand", axis=1
    )

    ### Tidy licence names
    def tidy_licence(licence_name):
        """Temporary licence conversion to match export2jkan -- FOR ANALYTICS ONLY, will discard in 2022Q2 Milestone
        Returns:
            string: a tidied licence name
        """
        known_licences = {
            "https://creativecommons.org/licenses/by-sa/3.0/": "Creative Commons Attribution Share-Alike 3.0",
            "https://creativecommons.org/licenses/by/4.0/legalcode": "Creative Commons Attribution 4.0 International",
            "https://creativecommons.org/licenses/by/4.0": "Creative Commons Attribution 4.0 International",
            "http://creativecommons.org/licenses/by-sa/3.0/": "Creative Commons Attribution Share-Alike 3.0",
            "http://creativecommons.org/licenses/by/4.0/legalcode": "Creative Commons Attribution 4.0 International",
            "http://creativecommons.org/licenses/by/4.0": "Creative Commons Attribution 4.0 International",
            "Creative Commons Attribution 4.0": "Creative Commons Attribution 4.0 International",
            "https://creativecommons.org/share-your-work/public-domain/cc0": "Creative Commons CC0",
            "https://rightsstatements.org/page/NoC-NC/1.0/": "Non-Commercial Use Only",
            "https://opendatacommons.org/licenses/odbl/1-0/": "Open Data Commons Open Database License 1.0",
            "http://creativecommons.org/share-your-work/public-domain/cc0": "Creative Commons CC0",
            "http://rightsstatements.org/page/NoC-NC/1.0/": "Non-Commercial Use Only",
            "http://opendatacommons.org/licenses/odbl/1-0/": "Open Data Commons Open Database License 1.0",
            "Open Data Commons Open Database License 1.0": "Open Data Commons Open Database License 1.0",
            "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/2/": "Open Government Licence v2.0",
            "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/": "Open Government Licence v3.0",
            "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/2/": "Open Government Licence v2.0",
            "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/": "Open Government Licence v3.0",
            "Open Government Licence 3.0 (United Kingdom)": "Open Government Licence v3.0",
            "UK Open Government Licence (OGL)": "Open Government Licence v3.0",
            "Open Government": "Open Government Licence v3.0",
            "uk-ogl": "Open Government Licence v3.0",
            "OGL3": "Open Government Licence v3.0",
            "https://rightsstatements.org/vocab/NKC/1.0/": "No Known Copyright",
            "https://creativecommons.org/publicdomain/mark/1.0/": "Public Domain",
            "http://rightsstatements.org/vocab/NKC/1.0/": "No Known Copyright",
            "http://creativecommons.org/publicdomain/mark/1.0/": "Public Domain",
            "Other (Public Domain)": "Public Domain",
            "Public Domain": "Public Domain",
            "Public Sector End User Licence (Scotland)": "Public Sector End User Licence (Scotland)",
        }

        for key in known_licences.keys():
            if str(licence_name).lower().strip(" /") == key.lower().strip(" /"):
                return known_licences[key]

        if str(licence_name) == "nan":
            tidied_licence = "No licence"
        else:
            tidied_licence = "Custom licence: " + str(licence_name)
        return tidied_licence

    data["License"] = data["License"].apply(tidy_licence)


    def tidy_file_type(file_type):
        """ Temporary data type conversion
        Args:
            file_type (str): the data type name
        Returns:
            tidied_file_type (str): a tidied data type name
        """
        file_types_to_tidy = {
            "application/x-7z-compressed": "7-Zip compressed file",
            "ArcGIS GeoServices REST API": "ARCGIS GEOSERVICE",
            "Esri REST": "ARCGIS GEOSERVICE",
            "Atom Feed": "ATOM FEED",
            "htm": "HTML",
            "ics": "iCalendar",
            "jpeg": "Image",
            "vnd.openxmlformats-officedocument.spreadsheetml.sheet": "MS EXCEL",
            "vnd.ms-excel": "MS EXCEL",
            "xls": "MS EXCEL",
            "xlsx": "MS EXCEL",
            "doc": "MS Word",
            "docx": "MS Word",
            "QGIS": "QGIS Shapefile",
            "text": "TXT",
            "web": "URL",
            "UK/DATA/#TABGB1900": "URL",
            "UK/ROY/GAZETTEER/#DOWNLOAD": "URL",
            "Web Mapping Application": "WEB MAP",
            "mets": "XML",
            "alto": "XML",
        }
        tidied_data_type = "NULL"

        for key in file_types_to_tidy.keys():
            if str(file_type).lower().strip(". /") == key.lower().strip(". /"):
                tidied_file_type = file_types_to_tidy[key]
                return tidied_file_type

        if (
            str(file_type) == "nan"
            or str(file_type) == ""
        ):
            tidied_file_type = "No file type"
        else:
            # print("file type: ", file_type)
            tidied_file_type = str(file_type).strip(". /").upper()

        return tidied_file_type

    ### Inconsistencies in casing for FileType
    data['FileType'] = data['FileType'].apply(tidy_file_type)

    return data


if __name__ == "__main__":
    merge_data()
