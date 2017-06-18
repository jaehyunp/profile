import requests
import sys
import json
import re
import os
import string
import argparse
import m3u8
import subprocess

VODAPI_OLD = 'https://api.twitch.tv/api/videos/{}'
VODAPI_NEW = "https://api.twitch.tv/api/vods/{}/access_token"
INDEX_API = "http://usher.twitch.tv/vod/{}"
CHUNK_RE = "(.+\.ts)\?start_offset=(\d+)&end_offset=(\d+)"

def download_file(url, local_filename):
    print("Downloading {}".format(local_filename))
    CS = 1024
    done = 0
    r = requests.get(url, stream = True)
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size = CS):
            if not chunk: continue # filter out keep-alive new chunks
            f.write(chunk)
            f.flush()
            done += CS
            sys.stdout.write("\r{0:>7.2f} MB".format(done / 1048576.0))
    print(" Done\n")
 
def sub_filenames_old(vidID):
    url = VODAPI_OLD.format(vidID)
    r = requests.get(url)
    data = r.json()
 
    qualities = data['chunks']
    if 'live' in qualities: best_resolution = 'live'
    else:
        res = [int(q[:-1]) for q in qualities if re.match("^\d+p", q)]
        best_resolution = "{}p".format(max(res))
 
    filenames = []
    ind = 0
    for nr, chunk in enumerate(data['chunks'][best_resolution]):
        video_url = chunk['url']
        ext = os.path.splitext(video_url)[1]
        filename = "%s_%04d%s" % (vidID, ind, ext)
        ind += 1
        filenames.append((video_url, filename))

    return (filenames, ext)

def sub_filenames_new(vidID):
    # Get access code
    url = VODAPI_NEW.format(vidID)
    r = requests.get(url)
    data = r.json()
 
    # Fetch vod index
    url = INDEX_API.format(vidID)
    payload = {'nauth': data['token'], 'nauthsig': data['sig']}
    r = requests.get(url, params=payload)
 
    m = m3u8.loads(r.content)
    url = m.playlists[0].uri
    index = m3u8.load(url)

    pieces = []
    for seg in index.segments:
        p = re.match(CHUNK_RE, seg.absolute_uri)
        (filename, start_byte, end_byte) = p.groups()
        if not pieces or pieces[-1][0] != filename:
            pieces.append([filename, start_byte, end_byte])
        else: pieces[-1][2] = end_byte
    
    filenames = []
    ind = 0
    for part in pieces:
        video_url = "{}?start_offset={}&end_offset={}".format(*part)
        ext = os.path.splitext(part[0])[1]
        filename = "%s_%04d%s" % (vidID, ind, ext)
        ind += 1
        filenames.append((video_url, filename))
    
    return (filenames, ext)
 
def get_filenames(vidtype, vidID):
    if vidtype == 'c':   return sub_filenames_old('c' + vidID)
    elif vidtype == 'a': return sub_filenames_old('a' + vidID)
    elif vidtype == 'v': return sub_filenames_new(vidID)
    else:
        print 'VOD type not understood; invalid Twitch VOD URL?'
        return ([], '')

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help='url of the vod')
    args = parser.parse_args()
    urlcomps = filter(None, args.url.split('/'))
    vidID = urlcomps[-1]
    vidtype = urlcomps[-2]
    (filenames, ext) = get_filenames(vidtype, vidID)
    for f in filenames: download_file(*f)
