#!/usr/bin/env python

import os
import os.path
import time
import string
import urllib
import sys
import cgi

__version__ = '0.1'

# Stylesheet info:
css_data = """
BODY {
    background: white;
}
IMG {
    border: 10px;
    width: 160px;
    height: 120px;
}
H1 {
    font-family: verdana, arial, helvetica, sans-serif;
    font-size: 24px;
    font-weight: bold;
    font-style: normal;
}
H2 {
    font-family: verdana, arial, helvetica, sans-serif;
    font-size: 18px;
    font-weight: bold;
    font-style: italic;
}
P {
    font-family: verdana, arial, helvetica, sans-serif;
    font-size: 11px;
    font-weight: normal;
    font-style: normal;
}

"""

# Get environment and CGI info
remote_addr = os.environ.get('REMOTE_ADDR')
script_name = os.environ.get('SCRIPT_NAME')
server_name = os.environ.get('SERVER_NAME')
script_location = 'http://' + server_name + script_name
path_url = 'http://' + server_name + os.path.dirname(script_name)
path_info = os.environ.get('PATH_INFO')
if path_info and (path_info[0] == '/'):
    path_info = path_info[1:]
if path_info == '':
    path_info = None
local_time = time.ctime()

# Check out options
cgi_vars = cgi.parse()
if cgi_vars.has_key('thumbnails'):
    thumbnails = (cgi_vars['thumbnails'])[0]
else:
    thumbnails = 'on'

# Initialize our subdirs and image list.
subdirs = []
images = []

# Loop over the directory entries at the path location.
if (not path_info):
    location = '.'
else:
    location = path_info
entries = os.listdir(location)
entries.sort()
for entry in entries:
    if os.path.isdir(os.path.join(location, entry)):
        subdirs.append(entry)
    else:
        base, ext = os.path.splitext(entry)
        ext = string.lower(ext)
        if (ext == '.jpg') or (ext == '.gif') or (ext == '.png'):
            images.append(entry)

print 'Content-type: text/html'
print ''
print '<html>'
print '<head>'
if path_info:
    print '<title>Photo Index: ' + location + '</title>'
else:
    print '<title>Photo Index</title>'
print '<style type="text/css">'
print css_data
print '</style>'
print '</head>'
print '<body>'
if path_info:
    print '<h1>Photo Index: ' + location + '</h1>'
else:
    print '<h1>Photo Index</h1>'
print '<p>WARNING: Pages with photos might take a while to load.</p>'
if len(subdirs):
    print '<h2>Subdirectories:</h2>'
    print '<ul>'
    subdirs.reverse()
    for subdir in subdirs:
        if thumbnails == 'off':
            qquery = '?thumbnails=off'
        else:
            qquery = ''
        if path_info:
            url = script_location + '/' + path_info + '/' \
                  + urllib.quote(subdir)
        else:
            url = script_location + '/' + urllib.quote(subdir)
        print '<li><a href="%s%s">%s</a></li>' % (url, qquery, subdir)
    print '</ul>'
if len(images):
    print '<h2>Photos:</h2>'
    if thumbnails == 'off':
        print '<ul>'
    else:
        print '<p>'
    for image in images:
        url = path_url + '/' + location + '/' + urllib.quote(image)
        if thumbnails == 'off':
            img_tag = '<li>' + image + '</li>'
        else:
            img_tag = '<img src="' + url + '"/>'
        print '<a href="%s">%s</a>' % (url, img_tag)
    if thumbnails == 'off':
        print '</ul>'
    else:
        print '</p>'
print '<h2>Options:</h2>'
print '<p>'
thumbnail_toggle_url = script_location
if path_info:
    thumbnail_toggle_url = thumbnail_toggle_url + '/' + path_info
if thumbnails != 'off':
    thumbnail_toggle_url = thumbnail_toggle_url + '?thumbnails=off'
print 'Thumbnail display is: <b>%s</b> [<a href="%s">toggle</a>]<br/>' \
      % (thumbnails, thumbnail_toggle_url)
print '</p>'
print '<hr/>'
print '<p><i>Photo indexing script by '
print '   <a href="http://www.red-bean.com/cmpilato/">C. Michael Pilato</a><br/>'
print '   <i>Current time: %s</i></p>' % (local_time)
print '</body>'
print '</html>'
