import io
import shutil
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload,MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
import os

def get_service(api_name, api_version, scopes, key_file_location):
    """Get a service that communicates to a Google API.

    Args:
        api_name: The name of the api to connect to.
        api_version: The api version to connect to.
        scopes: A list auth scopes to authorize for the application.
        key_file_location: The path to a valid service account JSON key file.

    Returns:
        A service that is connected to the specified API.
    """

    credentials = service_account.Credentials.from_service_account_file(
    key_file_location)

    scoped_credentials = credentials.with_scopes(scopes)

    # Build the service object.
    service = build(api_name, api_version, credentials=scoped_credentials)

    return service

def list_files():
    # Define the auth scopes to request.
    scope = 'https://www.googleapis.com/auth/drive.metadata.readonly'
    key_file_location = 'pi-backup-390018-6193916bb206.json'

    try:
        # Authenticate and construct service.
        service = get_service(
            api_name='drive',
            api_version='v3',
            scopes=[scope],
            key_file_location=key_file_location)

        # Call the Drive v3 API
        results = service.files().list(
            pageSize=100, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])

        if not items:
            print('No files found.')
            return
        print('Files:')
        for item in items:
            print(u'{0} ({1})'.format(item['name'], item['id']))
    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print('An error occurred: ', error)

def upload_file(filename):
    # Define the auth scopes to request.
    scope = 'https://www.googleapis.com/auth/drive'
    key_file_location = 'pi-backup-390018-6193916bb206.json'

    try:
        # Authenticate and construct service.
        service = get_service(
            api_name='drive',
            api_version='v3',
            scopes=[scope],
            key_file_location=key_file_location)

        file_metadata = {
        'name': filename,
        'mimeType': '*/*'
        }
        media = MediaFileUpload(filename,
                                mimetype='*/*',
                                resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print ('File ID: ' + file.get('id'))
    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print('An error occurred: ', error)

def delete_file(file_id):
    # Define the auth scopes to request.
    scope = 'https://www.googleapis.com/auth/drive'
    key_file_location = 'pi-backup-390018-6193916bb206.json'

    try:
        # Authenticate and construct service.
        service = get_service(
            api_name='drive',
            api_version='v3',
            scopes=[scope],
            key_file_location=key_file_location)

        service.files().delete(fileId=file_id).execute()
        print ('Deleted: ', file_id)
    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print('An error occurred: ', error)

def upload_directory(directory_path, filetype):
    # Define the auth scopes to request.
    scope = 'https://www.googleapis.com/auth/drive'
    key_file_location = 'pi-backup-390018-6193916bb206.json'
    num_new = 0

    try:
        # Authenticate and construct service.
        service = get_service(
            api_name='drive',
            api_version='v3',
            scopes=[scope],
            key_file_location=key_file_location)

        # get list of existing files
        results = service.files().list(
            pageSize=100, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])

        filenames = set([item["name"] for item in items])

        files_to_upload = os.listdir(directory_path)

        # make sure object is file, is correct filetype and is not already uploaded
        for file in files_to_upload:
            file_path = directory_path + "/" + file
            if os.path.isfile(file_path) and file[-4:] == filetype:
                if file in filenames:
                    print("Skipping ", file, ", item has already been downloaded")
                else:
                    file_metadata = {
                    'name': file,
                    'mimeType': '*/*'
                    }
                    media = MediaFileUpload(file_path,
                                            mimetype='*/*',
                                            resumable=True)
                    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                    print ('File ID: ' + file.get('id'))
                    num_new += 1
    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print('An error occurred: ', error)
    print(num_new, " new files uploaded")
    print("Total number of files: ", len(items))

def download_directory(directory_path):
    # Define the auth scopes to request.
    scope = 'https://www.googleapis.com/auth/drive'
    key_file_location = 'pi-backup-390018-6193916bb206.json'
    num_new_downloaded = 0

    try:
        # Authenticate and construct service.
        service = get_service(
            api_name='drive',
            api_version='v3',
            scopes=[scope],
            key_file_location=key_file_location)

        # get list of existing files
        results = service.files().list(
            pageSize=100, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])

        files_already_downloaded = os.listdir(directory_path)

        # make sure object is file, is correct filetype and is not already uploaded
        for item in items:
            file = item["name"]
            save_path = directory_path + "/" + file
            if item["name"] in files_already_downloaded:
                print("Skipping ", file, ", item has already been downloaded")
            else:
                request = service.files().get_media(fileId=item["id"])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    print("Download %d%%" % int(status.progress() * 100))

                # The file has been downloaded into RAM, now save it in a file
                fh.seek(0)
                with open(save_path, 'wb') as f:
                    shutil.copyfileobj(fh, f, length=131072)
                    print ('File ID: ' + item.get('id'))
                num_new_downloaded += 1
    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print('An error occurred: ', error)
    print(num_new_downloaded, " new files downloaded")
    print("Total number of files: ", len(items))

def main():
    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    # list_files()
    # upload_directory("C:/Users/antho/OneDrive/Documents/2023-2024/BBC/Bike/folder_to_backup",".txt")
    # download_directory("C:/Users/antho/OneDrive/Documents/2023-2024/BBC/Bike/folder_to_sync")

    

if __name__ == '__main__':
    main()