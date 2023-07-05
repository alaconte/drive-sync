import io
import shutil
import os
import argparse
import json
import requests as req
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload,MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

def make_archive(source, destination):
    base = os.path.basename(destination)
    name = base.split('.')[0]
    format = base.split('.')[1]
    archive_from = os.path.dirname(source)
    archive_to = os.path.basename(source.strip(os.sep))
    print(source, destination, archive_from, archive_to)
    shutil.make_archive(name, format, archive_from, archive_to)
    shutil.move('%s.%s'%(name,format), destination)

class DriveSync():
    def __init__(self):
        # TODO:: load file location from json eventually
        # Define the auth scopes to request.
        if not os.path.isfile("./settings.json"):
            self.create_empty_settings()
        with open("./settings.json", "r") as f:
            self.settings = json.load(f)
        scope = 'https://www.googleapis.com/auth/drive'
        key_file_location = self.settings["client_secret"]

        try:
            # Authenticate and construct service.
            self.service = self.get_service(
                api_name='drive',
                api_version='v3',
                scopes=[scope],
                key_file_location=key_file_location)
        except HttpError as error:
            print('An error occurred: ', error)

    def create_empty_settings(self):
        print("Could not find settings.json: creating empty settings file")
        print("Please specify paths in settings.json and restart script")
        settings = {"backup_dir" : "<PATH TO DIRECTORY TO BACKUP>",
                    "sync_dir" : "<PATH TO DIRECTORY TO SYNC TO>",
                    "client_secret" : "<PATH TO CLIENT SECRET>",
                    "file_types" : "<LIST OF FILETYPES TO BACKUP>"}
        settings_json = json.dumps(settings)
        with open("settings.json", "w") as f:
            f.write(settings_json)
        exit()

    def get_service(self, api_name, api_version, scopes, key_file_location):
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

    def get_files(self):
        try:
            # Get all items from root of drive
            all_items = []
            first = True
            while True:
                if first:
                    print("Retrieving batch of items")
                    results = self.service.files().list(
                        pageSize=100, fields="nextPageToken, files(id, name, mimeType)").execute()
                    first = False
                else:
                    print("Retrieving batch of items")
                    results = self.service.files().list(
                        pageSize=100, pageToken = page_token, fields="nextPageToken, files(id, name, mimeType)").execute()
                items = results.get('files', [])
                page_token = results.get('nextPageToken', None)

                all_items += items

                if page_token == None:
                    break

            files = []
            folders = []
            for item in all_items:
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    folders.append(item)
                else:
                    files.append(item)

            # output info
            if not files:
                print('No files found.')
                return [], []
            print('Files:')
            for file in files:
                print(u'{0} ({1})'.format(file['name'], file['id']))
            print('\nFolders:')
            for folder in folders:
                print(f"{folder['name']} ({folder['id']})")
            print(f"Total of {len(files)} files found")
            print(f"Total of {len(folders)} folders found")

            return files, folders
        except HttpError as error:
            # TODO(developer) - Handle errors from drive API.
            print('An error occurred: ', error)

    def upload_file(self, filename):
        try:
            file_metadata = {
            'name': filename,
            'mimeType': '*/*'
            }
            media = MediaFileUpload(filename,
                                    mimetype='*/*',
                                    resumable=True)
            file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            print ('File ID: ' + file.get('id'))
        except HttpError as error:
            # TODO(developer) - Handle errors from drive API.
            print('An error occurred: ', error)

    def delete_file(self, file_id):
        try:
            self.service.files().delete(fileId=file_id).execute()
            print ('Deleted: ', file_id)
        except HttpError as error:
            # TODO(developer) - Handle errors from drive API.
            print('An error occurred: ', error)

    def delete_file_by_name(self, filename):
        files, folders = self.get_files()

        for item in files:
            if item["name"] == filename:
                self.delete_file(item["id"])

    def delete_all(self):
        try:
            # get all files and folders
            files, folders = self.get_files()

            print(f"Warning: about to delete {len(files)} files and {len(folders)} folders")
            confirm = input("Please input \"yes\" to continue\n>>> ")
            if confirm != "yes":
                return

            # delete all files first
            num_files, num_folders = len(files), len(folders)
            for idx, file in enumerate(files):
                self.service.files().delete(fileId=file['id']).execute()
                print ('Deleted: ', file['name'])
                if idx % 10 == 0:
                    print(f'\nProgress: {idx} files deleted out of {num_files}\n')
            for idx, folder in enumerate(folders):
                self.service.files().delete(fileId=folder['id']).execute()
                print('Deleted: ', folder['name'])
                if idx % 10 == 0:
                    print(f'\nProgress: {idx} folders deleted out of {num_folders}\n')
        except HttpError as error:
            # TODO(developer) - Handle errors from drive API.
            print('An error occurred: ', error)

    def delete_local_copies(self):
        try:
            # get all files and folders
            files, folders = self.get_files()
            directory_path = self.settings["backup_dir"]
            items_to_clear = os.listdir(directory_path)

            print(f"Deleting local copies of files in directory {directory_path}")

            num_deleted = 0
            # delete all files first
            num_files, num_folders = len(files), len(folders)
            for idx, file in enumerate(files):
                if file["name"] in items_to_clear:
                    os.remove(directory_path + "/" + file["name"])
                    print ('Deleted: ', file['name'])
                if file["name"][-4:] == ".zip" and file["name"][0:-4] in items_to_clear:
                    shutil.rmtree(directory_path + "/" + file["name"][0:-4])
                    print('Deleted: ', file["name"][0:-4])
        except HttpError as error:
            # TODO(developer) - Handle errors from drive API.
            print('An error occurred: ', error)

    def upload_directory(self):
        num_new = 0
        directory_path = self.settings["backup_dir"]
        filetypes = self.settings["file_types"]

        try:
            # get list of existing files
            files, folders = self.get_files()

            filenames = set([file["name"] for file in files])
            foldernames = set([folder["name"] for folder in folders])

            items_to_upload = os.listdir(directory_path)

            # make sure object is file, is correct filetype and is not already uploaded
            for item in items_to_upload:
                item_path = directory_path + "/" + item

                # if file, check for duplicate then upload
                if os.path.isfile(item_path):
                    if filetypes != None and item[-4:] not in filetypes:
                        print(f"Skipping {item}, file not in specified filetypes {filetypes}")
                        print(f"Specify None as filetype to skip filetype checking")
                    elif item in filenames:
                        print(f"Skipping {item}, file has already been uploaded")
                    else:
                        file_metadata = {
                        'name': item,
                        'mimeType': '*/*'
                        }
                        media = MediaFileUpload(item_path,
                                                mimetype='*/*',
                                                resumable=True)
                        file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                        print ('File ID: ' + file.get('id'))
                        num_new += 1

                # if directory, check for duplicates then zip directory and upload zip
                elif os.path.isdir(item_path):
                    if item + ".zip" in filenames:
                        print(f"Skipping {item}, folder has already been uploaded")
                    else:
                        folder_items = os.listdir(directory_path + "/" + item)

                        # check filetypes of folder items
                        excluded_file_found = False
                        for subitem in folder_items:
                            subitem_path = directory_path + "/" + item + "/" + subitem
                            if os.path.isfile(subitem_path) and (filetypes != None and subitem[-4:] not in filetypes):
                                print(f"Folder {item} contains file {subitem}, which is not in specified filetypes {filetypes}")
                                print(f"Specify None as filetype to skip filetype checking")
                                excluded_file_found = True
                        
                        if not excluded_file_found:
                            print(f"Creating zip of directory {item} containing {len(folder_items)} files")

                            # create temporary zip file
                            make_archive(item_path, item_path + ".zip")
                            file_metadata = {
                            'name': item+".zip",
                            'mimeType': '*/*',
                            }
                            media = MediaFileUpload(item_path+".zip",
                                                    mimetype='*/*',
                                                    resumable=True)
                            file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                            print ('File ID: ' + file.get('id'))
                            num_new += 1
                            # remove temporary local zip file
                            media = None
                            os.remove(item_path + ".zip")

        except HttpError as error:
            # TODO(developer) - Handle errors from drive API.
            print('An error occurred: ', error)
        print(f"{num_new} new files/folders uploaded")
        print(f"Total number of files/folders: {len(files) + len(folders) + num_new}")

    def download_directory(self):
        directory_path = self.settings["sync_dir"]
        num_new_downloaded = 0

        try:
            # get list of existing files
            files, folders = self.get_files()

            filenames = set([file["name"] for file in files])
            foldernames = set([folder["name"] for folder in folders])

            files_already_downloaded = os.listdir(directory_path)

            # make sure object is file, is correct filetype and is not already uploaded
            for item in files:
                file = item["name"]
                save_path = directory_path + "/" + file
                if item["name"] in files_already_downloaded:
                    print("Skipping ", file, ", item has already been downloaded")
                else:
                    request = self.service.files().get_media(fileId=item["id"])
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
        print(f"Total number of files: {len(filenames)}")

    def upload_ip(self):
        url = "https://checkip.amazonaws.com"
        request = req.get(url)
        ip = request.text

        # create file with ip
        print(f"Public IP: {ip}")
        with open('ip.txt', 'w') as f:
            f.write(ip)

        # delete old ip text files
        self.delete_file_by_name('ip.txt')
        
        # upload file
        self.upload_file('ip.txt')
        os.remove('ip.txt')

    def download_ip(self):
        directory_path = self.settings["sync_dir"]
        files, folders = self.get_files()
        for item in files:
            file = item["name"]
            save_path = directory_path + "/" + file
            if file == "ip.txt":
                request = self.service.files().get_media(fileId=item["id"])
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


        


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--backup", help = "Launch in backup mode. Will upload all non-duplicate files in the directory specified within settings.json", action = "store_true")
    parser.add_argument("-c", "--clear", help = "Clear all local copies of files that have already been uploaded", action = "store_true")
    parser.add_argument("-s", "--sync", help = "Launch in sync mode. Will download all non-downloaded files to the directory specified within settings.json", action = "store_true")
    parser.add_argument("-p", "--purge", help = "Delete all files stored remotely.", action = "store_true")
    parser.add_argument("-i", "--ip", help = "Update the remotely stored IP address file", action = "store_true")
    parser.add_argument("-a", "--address", help = "Download the remotely stored IP address file", action="store_true")

    args = parser.parse_args()

    if args.backup:
        # do backup
        drive_sync = DriveSync()
        drive_sync.upload_directory()

    if args.clear:
        drive_sync = DriveSync()
        drive_sync.delete_local_copies()

    if args.sync:
        # do sync
        drive_sync = DriveSync()
        drive_sync.download_directory()

    if args.purge:
        drive_sync = DriveSync()
        drive_sync.delete_all()

    if args.ip:
        drive_sync = DriveSync()
        drive_sync.upload_ip()

    if args.address:
        drive_sync = DriveSync()
        drive_sync.download_ip()

    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    # list_files()
    # upload_directory("C:/Users/antho/OneDrive/Documents/2023-2024/BBC/Bike/folder_to_backup",".txt")
    # download_directory("C:/Users/antho/OneDrive/Documents/2023-2024/BBC/Bike/folder_to_sync")

    

if __name__ == '__main__':
    main()