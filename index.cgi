#!/usr/bin/env python

import os
import os.path
import time
import urllib
import sys
import cgi

__version__ = '2.1'

###
###  URL SCHEME:
###
###     CGIURL[/PATH_INFO][?OPTIONS]
###
###  If PATH_INFO is a directory, shows a directory listing (subdirs
###  at the top, images at the bottom).  If a FILE, shows a thumbnail
###  of the file.
###
###  OPTIONS:
###
###     t=[on|off]    Thumbnail display on/off toggle
###     s=SIZE        Image size (subject to MAX_IMAGE_SIZE)
###

############################################################################
##  CONFIGURATION SECTION
##
THUMBNAIL_SIZE = 160
MAX_IMAGE_SIZE = 640
IMAGE_EXTENSIONS = ['.jpg', '.gif', '.png']
CSS_DATA = """
body {
    background: white; }
img {
    border: 10px;
    width: %dpx;
    height: 120px; }
h1 {
    font-family: verdana, arial, helvetica, sans-serif;
    font-size: 24px;
    font-weight: bold;
    font-style: normal; }
h2 {
    font-family: verdana, arial, helvetica, sans-serif;
    font-size: 18px;
    font-weight: bold;
    font-style: italic; }
p, li {
    font-family: verdana, arial, helvetica, sans-serif;
    font-size: 11px;
    font-weight: normal;
    font-style: normal; }
#directory {
    margin-left: 0.25in;
    margin-right: 0.25in; }
#thumbnails {
    padding: 20px 0; }
.itemup {
    background: url('/icons/small/back.gif') no-repeat;
    font-family: times new roman, times, serif;
    font-size: 16px;
    font-style: italic;
    padding-left: 20px;
    margin-top: 0;
    margin-bottom: 0; }
.itemdir {
    background: url('/icons/small/dir.gif') no-repeat;
    font-family: times new roman, times, serif;
    font-size: 16px;
    padding-left: 20px;
    margin-top: 0;
    margin-bottom: 0; }
.itemfile {
    background: url('/icons/small/image2.gif') no-repeat;
    font-family: times new roman, times, serif;
    font-size: 16px;
    padding-left: 20px;
    margin-top: 0;
    margin-bottom: 0; }
""" % (THUMBNAIL_SIZE)
##
############################################################################

def _cgi_parse():
    cgi_data = cgi.parse()
    cgi_vars = {}
    for name in cgi_data.keys():
        if cgi_data[name]:
            cgi_vars[name] = cgi_data[name][0]
    return cgi_vars

def _cgi_string(cgi_vars):
    pieces = []
    for name in cgi_vars.keys():
        pieces.append(name + '=' + cgi_vars[name])
    outstring = '&'.join(pieces)
    return outstring and '?' + outstring or outstring

class Request:
    def __init__(self):
        """Do some setup-ish stuff."""
        
        # Get environment info.
        remote_addr = os.environ.get('REMOTE_ADDR')
        script_name = os.environ.get('SCRIPT_NAME')
        server_name = os.environ.get('SERVER_NAME')
        
        # Build the script hrefs (one for running the script, one for
        # appending photo path stuffs.
        self.script_href = 'http://' + server_name + urllib.quote(script_name)
        self.script_dir_href = os.path.dirname(self.script_href)
        
        # Parse the path info.
        path_info = os.environ.get('PATH_INFO')
        if path_info and path_info.find('..') != -1:
            raise Exception, "Invalid URL"
        if path_info and (path_info[0] == '/'):
            path_info = path_info[1:]
        if path_info == '':
            path_info = None
        self.path_info = path_info
        self.real_path = path_info or '.'
        
        # Get the current timestamp.
        self.local_time = time.ctime()
        
        # CGI options, fetch and validate.
        self.cgi_vars = _cgi_parse()
        if int(self.cgi_vars.get('s', 0)) > MAX_IMAGE_SIZE:
            self.cgi_vars['s'] = str(MAX_IMAGE_SIZE)
            
        # What kind of request is this?
        if os.path.isfile(self.real_path):
            self.do_file()
        else:
            self.do_directory()

    def _gen_url(self, path_info, cgi_vars):
        base_href = self.script_href
        if path_info:
            base_href = base_href + '/' + urllib.quote(path_info)
        return base_href + _cgi_string(cgi_vars)
        
    def do_file(self):
        """Handle file displays."""
        import mimetypes
        mimetype = mimetypes.guess_type(self.real_path)[0]
        base, ext = os.path.splitext(self.real_path)
        if ext.lower() not in IMAGE_EXTENSIONS or not mimetype:
            raise Exception, "Unsupported file format!"

        if self.cgi_vars.has_key('s'):
            size = int(self.cgi_vars['s'])
            try:
                import Image
                im = Image.open(open(self.real_path, 'rb'))
                im.thumbnail((size, size))
                print "Content-type: %s\n" % (mimetype)
                im.save(sys.stdout, im.format)
            except OSError:
                raise Exception, "Unsupported file format!"
        else:
            print "Content-type: %s\n" % (mimetype)
            fp = open(self.real_path, 'rb')
            while 1:
                data = fp.read(102400)
                if not data:
                    break
                sys.stdout.write(data)
            
            
    def do_directory(self):
        """Handle directory listings."""

        # Initialize our subdirs and image list.
        subdirs = []
        images = []

        # Loops over the directory entries, sorting into subdirs and
        # images with recognized file extensions
        entries = os.listdir(self.real_path)
        entries.sort()
        for entry in entries:
            if os.path.isdir(os.path.join(self.real_path, entry)):
                subdirs.append(entry)
            else:
                base, ext = os.path.splitext(entry)
                if ext.lower() in IMAGE_EXTENSIONS:
                    images.append(entry)
        
        # -----------------------------------------------------------------
        # Print the header.
        # -----------------------------------------------------------------
        
        print 'Content-type: text/html'
        print ''
        print '<html>'
        print '<head>'
        if self.path_info:
            print '<title>Photo Index: ' + self.real_path + '</title>'
        else:
            print '<title>Photo Index</title>'
        print '<style type="text/css">'
        print CSS_DATA
        print '</style>'
        print '</head>'
        print '<body>'
        if self.path_info:
            print '<h1>Photo Index: ' + self.real_path + '</h1>'
        else:
            print '<h1>Photo Index</h1>'
        
        # -----------------------------------------------------------------
        # Print the settings display information
        # -----------------------------------------------------------------

        print '<ul>'
        print '<li>Thumbnail display is <strong>%s</strong></li>' \
              % (self.cgi_vars.get('t', 'on') == 'on' and 'on' or 'off')
        print '<li>Clicked images have max size of <strong>%s</strong></li>' \
              % (self.cgi_vars.get('s', 'no maximum'))
        print '</ul>'
        print '<hr/>'
        
        # -----------------------------------------------------------------
        # Print the directory listing section, which includes subdirectories
        # and, if not displaying thumbnails, image files.
        # -----------------------------------------------------------------
        
        print '<div id="directory">'
        subdirs.reverse()
        if self.path_info:
            print '<p class="itemup"><a href="%s">[PARENT DIRECTORY]</a></p>' \
                  % (self._gen_url(os.path.dirname(self.path_info),
                                   self.cgi_vars))
        for subdir in subdirs:
            base_path = self.path_info or ''
            print '<p class="itemdir"><a href="%s">%s</a></p>' \
                  % (self._gen_url(os.path.join(base_path, subdir),
                                   self.cgi_vars),
                     subdir)
        if self.cgi_vars.get('t', 'on') == 'off':
            for image in images:
                base_path = self.path_info or ''
                print '<p class="itemfile"><a href="%s">%s</a></p>' \
                      % (self._gen_url(os.path.join(base_path, image),
                                       self.cgi_vars), image)
        print '</div>'
        
        # -----------------------------------------------------------------
        # If we are displaying thumbnails, display them.
        # -----------------------------------------------------------------
        
        if self.cgi_vars.get('t', 'on') == 'on' and len(images):
            print '<div id="thumbnails">'
            cgi_vars = self.cgi_vars.copy()
            cgi_vars['s'] = str(THUMBNAIL_SIZE)
            for image in images:
                base_path = self.path_info or ''
                thumb_href = self._gen_url(os.path.join(base_path, image),
                                           cgi_vars)
                this_href = self._gen_url(os.path.join(base_path, image),
                                          self.cgi_vars)
                print '<a href="%s"><img src="%s"/></a></li>' \
                      % (this_href, thumb_href)
            print '</div>'
        
        # -----------------------------------------------------------------
        # Print the settings modification form.
        # -----------------------------------------------------------------
        
        print '<hr/>'
        print '<h2 id="options">Change Your Settings:</h2>'
        print '<form method="get" action="%s">' \
              % (self._gen_url(self.path_info, {}))
        print '<p>'
        print 'Thumbnail display: '
        t_opt = self.cgi_vars.get('t', 'on')
        for options in [['', 'on', t_opt == 'on'],
                        ['off', 'off', t_opt != 'on']]:
            print '<input type="radio" name="t" value="%s"%s>%s' \
                  % (options[0], options[2] and ' checked' or '', options[1])
        print '</p>'
        print '<p>'
        print 'Maximum image size: '
        s_opt = self.cgi_vars.get('s', '')
        for options in [['320', '320', s_opt == '320'],
                        ['640', '640', s_opt == '640'],
                        ['', 'none', s_opt not in ['320', '640']]]:
            print '<input type="radio" name="s" value="%s"%s>%s' \
                  % (options[0], options[2] and ' checked' or '', options[1])
        print '<input type="submit" value="Change settings">'
        print '</p>'
        print '</form>'
        
        # -----------------------------------------------------------------
        # Print the footer.
        # -----------------------------------------------------------------
        
        print '<hr/>'
        print '<p><i>Photo indexing script version %s by' % (__version__)
        print '   <a href="http://www.red-bean.com/cmpilato/">' \
              'C. Michael Pilato</a><br/>'
        print '   <i>Current time: %s</i></p>' % (self.local_time)
        print '</body>'
        print '</html>'


def test(path_info, query_string):
    os.environ['SCRIPT_NAME'] = '/SCRIPT_NAME'
    os.environ['SERVER_NAME'] = 'SERVER_NAME'
    os.environ['PATH_INFO'] = path_info
    os.environ['QUERY_STRING'] = query_string
    req = Request()
    
def main():
    try:
        req = Request()
    except Exception, e:
        print 'Content-type: text/plain\n\n%s\n' % (e)
    
if __name__ == "__main__":
    if os.environ.has_key('DEBUG'):
        test(sys.argv[1], sys.argv[2])
    else:
        main()
