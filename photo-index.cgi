#!/usr/bin/env python

### photo-index.cgi:  CGI script for dynamically serving thumbnailed
###                   collections of images.
###
### Copyright (c) 2005 C. Michael Pilato <cmpilato@red-bean.com>
###

import os
import os.path
import time
import urllib
import sys
import cgi
import string
import fnmatch
import ConfigParser
import ezt

__version__ = '4.2.0'

###
###  URL SCHEME:
###
###     CGIURL[/ALBUM][/PATH_INFO][?OPTIONS]
###
###  If PATH_INFO is a directory, shows a directory listing (subdirs
###  at the top, images at the bottom).  If a FILE, shows a thumbnail
###  of the file.
###
###  OPTIONS:
###
###     t=[on|off]    Thumbnail display on/off toggle
###     s=SIZE        Image size (subject to MAX_IMAGE_SIZE; 0 = original)
###     d=[on|off]    Direct image mode (no wrapping HTML) on/off toggle
###     r=[0|1|2|3]   Image rotation (number x 90 degrees counterclockwise)
###


############################################################################

# Global Variables
COOKIE_KEY = 'photo_opts='
IMAGE_EXTENSIONS = ['.jpg', '.gif', '.png']

class UnknownAlbumException(Exception):
    pass
class MissingAlbumException(Exception):
    pass

class OptionSet:
    def __init__(self, options):
        vars(self).update(options)
    
class Config:
    def __init__(self):
        cgi_dir = os.path.dirname(sys.argv[0])
        template_file = os.path.join(cgi_dir, 'photo-index.ezt')
        conf_file = os.path.join(cgi_dir, 'photo-index.conf') 

        self.parser = None
        self.albums = {}
        self.defaults = {
            'max_image_size' : 640,
            'thumbnail_size' : 120,
            'template_file' : template_file,
            'location' : None,
            'ignores' : '.*, CVS',
            'obscure' : 1,
            }

        # Parse the conf-file, if one exists.
        if not os.path.isfile(conf_file):
            return
        
        self.parser = parser = ConfigParser.ConfigParser()
        parser.read(conf_file)
        if parser.has_section('defaults'):
            self._parse_options_section('defaults', self.defaults)
        if parser.has_section('albums'):
            for key, value in parser.items('albums', raw=1):
                self.albums[key] = value

    def _parse_options_section(self, section, options):
        for option in ['max_image_size',
                       'thumbnail_size',
                       'template',
                       'ignores',
                       'obscure',
                       ]:
            if self.parser.has_option(section, option):
                value = self.parser.get(section, option)
                try:
                    value = int(value)
                except ValueError:
                    pass
                options[option] = value

    def get_albums(self):
        return self.albums.keys()

    def get_default_options(self):
        return OptionSet(self.defaults.copy())
    
    def get_album_options(self, album):
        options = self.defaults.copy()

        # If there's no album supplied, that's a problem.
        if not album:
            raise MissingAlbumException

        # If we don't recognize the album (either because we have no
        # config file, or because the album isn't present in that
        # file), that, too, is a problem.
        try:
            options['location'] = self.albums[album]
        except KeyError:
            raise UnknownAlbumException, album

        # If the album has an options overrides section, merge it into
        # the defaults.
        if self.parser.has_section(album):
            self._parse_options_section(album, options)

        # Finally, return the options.
        return OptionSet(options)
        

def _cookie_parse(cookie):
    # Parse the cookie into name/value pairs.
    cookie_vars = {}
    if cookie:
        start = cookie.find(COOKIE_KEY)
        if start != -1:
            end = cookie[start:].find(';')
            start = len(COOKIE_KEY)
            if end == -1:
                cookie = cookie[start:]
            else:
                cookie = cookie[start:start+end]
            pieces = cookie.split(',')
            for piece in pieces:
                nameval = piece.split('=')
                cookie_vars[nameval[0]] = len(nameval) > 1 and nameval[1] or ''
    return cookie_vars

def _cookie_string(cookie_vars):
    pieces = []
    for name in cookie_vars.keys():
        if cookie_vars[name]:
            pieces.append(name + '=' + cookie_vars[name])
    outstring = ','.join(pieces) or ''
    if outstring:
        outstring = '%s%s; path=/; expires=31-Dec-2012 23:59:59 GMT' \
                    % (COOKIE_KEY, outstring)
    return outstring
    
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
        cookie = os.environ.get('HTTP_COOKIE')

        # Build the script hrefs (one for running the script, one for
        # appending photo path stuffs.
        self.script_name = script_name
        self.script_href = 'http://' + server_name + urllib.quote(script_name)
        self.script_dir_href = os.path.dirname(self.script_href)
        
        # Parse the path info.
        path_info = os.environ.get('PATH_INFO')
        path_pieces = []
        if path_info:
            path_pieces = filter(None, path_info.split('/'))
        if '..' in path_pieces:
            raise Exception, "Invalid URL"
        self.album = None
        if len(path_pieces):
            self.album = path_pieces[0]

        # Get the configuration bits.
        do_listing = 0
        self.config = Config()
        try:
            self.options = self.config.get_album_options(self.album)
            del path_pieces[0]
        except MissingAlbumException:
            self.album = None
            self.options = self.config.get_default_options()
            do_listing = 1
        path_info = '/'.join(path_pieces)
        if path_info == '':
            path_info = None
        self.path_info = path_info
        self.real_path = self.options.location
        if self.path_info:
            self.real_path = os.path.join(self.real_path, path_info)
        
        # Get the current timestamp.
        self.local_time = time.ctime()

        # Handle the cookie.
        self.cookie_vars = _cookie_parse(cookie)
        
        # CGI options, fetch and validate.
        self.cgi_vars = _cgi_parse()
        if int(self.cgi_vars.get('s', 0)) > self.options.max_image_size:
            self.cgi_vars['s'] = str(self.options.max_image_size)

        # Merge cookie data into CGI data; CGI wins.
        if not self.cgi_vars.has_key('s') \
           and self.cookie_vars.get('s'):
            self.cgi_vars['s'] = self.cookie_vars['s']
        if not self.cgi_vars.has_key('t') \
           and self.cookie_vars.get('t'):
            self.cgi_vars['t'] = self.cookie_vars['t']

        # What kind of request is this?
        if do_listing:
            self.do_album_listing()
        elif os.path.isfile(self.real_path):
            self.do_file()
        else:
            self.do_directory()

    def _gen_url(self, path_info, cgi_vars):
        base_href = self.script_href
        if self.album:
            base_href = base_href + '/' + urllib.quote(self.album)
        if path_info:
            base_href = base_href + '/' + urllib.quote(path_info)
        return base_href + _cgi_string(cgi_vars)

    def _init_template_data(self, is_dir):
        data = {
            'version' : __version__,
            'thumbnail_size' : self.options.thumbnail_size,
            'album' : self.album,
            'path' : self.path_info,
            'mode' : is_dir and "dir" or "file",
            'localtime' : self.local_time,
            }
        return data

    def _generate_output(self, data, extra_headers=[]):
        template = ezt.Template(self.options.template, 1, ezt.FORMAT_RAW)
        sys.stdout.write("Content-type: text/html\n")
        for header in extra_headers:
            sys.stdout.write(header + "\n")
        sys.stdout.write("\n")
        template.generate(sys.stdout, data)
        sys.exit(0)
        
    def do_file(self):
        """Handle file displays."""
        import mimetypes
        mimetype = mimetypes.guess_type(self.real_path)[0]
        base, ext = os.path.splitext(self.real_path)
        if ext.lower() not in IMAGE_EXTENSIONS or not mimetype:
            raise Exception, "Unsupported file format!"
        size = int(self.cgi_vars.get('s', '0'))
        rotate = int(self.cgi_vars.get('r', '0'))

        if self.cgi_vars.get('d', 'off') == 'on':
            # Direct mode -- we're serving a picture.
            try:
                import Image
                im = Image.open(open(self.real_path, 'rb'))
                if size:
                    im.thumbnail((size, size))
                print "Content-type: %s\n" % (mimetype)
                im.rotate(rotate * 90).save(sys.stdout, im.format)
            except OSError:
                raise Exception, "Unsupported file format!"
        else:
            # Indirect mode -- we're serving an HTML picture wrapper.
            if not size:
                raise Exception, "Script error -- no indirect mode " \
                      "support for unsized images."
            rotate_l = (rotate + 1) % 4
            rotate_r = (rotate - 1) % 4

            # Generate output
            data = self._init_template_data(0)
            data.update({
                'up_href' : self._gen_url(os.path.dirname(self.path_info), {}),
                'prev_href' : None,
                'next_href' : None,
                'rotate_left_href' : self._gen_url(self.path_info,
                                                   {'s' : str(size),
                                                    'd' : 'off',
                                                    'r' : str(rotate_l)}),
                'rotate_right_href' : self._gen_url(self.path_info,
                                                    {'s' : str(size),
                                                     'd' : 'off',
                                                     'r' : str(rotate_r)}),
                'image_full_href' : self._gen_url(self.path_info,
                                                  {'s' : '0',
                                                   'd' : 'on',
                                                   'r' : str(rotate)}),
                'image_href' : self._gen_url(self.path_info,
                                             {'s' : str(size),
                                              'd' : 'on',
                                              'r' : str(rotate)}),
                })
            self._generate_output(data)

    def _get_settings(self):
        settings = []
        thumbnail_options = []
        thumbnail_options.append(_item(name='on', value='on'))
        thumbnail_options.append(_item(name='off', value='off'))
        settings.append(_item(description='Thumbnail display',
                              name='t',
                              value=self.cgi_vars.get('t', 'on') == 'on' \
                                  and 'on' or 'off',
                              options=thumbnail_options))
        size_options = []
        size_options.append(_item(name='320', value='320'))
        size_options.append(_item(name='640', value='640'))
        size_options.append(_item(name='no maximum', value='0'))
        settings.append(_item(description='Maximum image size (0 = none)',
                              name='s',
                              value=int(self.cgi_vars.get('s', '0')),
                              options=size_options))
        return settings
        
    def do_directory(self):
        """Handle directory listings."""
        # -----------------------------------------------------------------
        # Setup the directory listing section, which includes subdirectories
        # and, if not displaying thumbnails, image files.
        # -----------------------------------------------------------------
        subdirs = []
        images = []

        base_path = self.path_info or ''
        entries = os.listdir(self.real_path)
        entries.sort()
        ignores = map(string.strip,
                      filter(None,
                             string.split(self.options.ignores or '', ',')))

        def _is_ignored(filename):
            for ignore in ignores:
                if fnmatch.fnmatch(filename, ignore):
                    return 1
            return 0
            
        for entry in entries:
            # Skip ignored stuff
            if _is_ignored(entry):
                continue
            real_path = os.path.join(self.real_path, entry)
            if not os.access(real_path, os.R_OK):
                continue
            if os.path.isdir(real_path):
                # Subdirectory
                subdir = _item(name=entry,
                               href=self._gen_url(os.path.join(base_path,
                                                               entry),
                                                  self.cgi_vars))
                subdirs.append(subdir)
            else:
                # File
                base, ext = os.path.splitext(entry)
                if ext.lower() not in IMAGE_EXTENSIONS:
                    continue

                cgi_vars = self.cgi_vars.copy()
                cgi_vars['d'] = 'off'
                thumb_cgi_vars = self.cgi_vars.copy()
                thumb_cgi_vars['s'] = str(self.options.thumbnail_size)
                thumb_cgi_vars['d'] = 'on'
                if not int(self.cgi_vars.get('s', '0')):
                    cgi_vars['d'] = 'on'

                thumb_href = self._gen_url(os.path.join(base_path, entry),
                                           thumb_cgi_vars)
                img_href = self._gen_url(os.path.join(base_path, entry),
                                         cgi_vars)
                images.append(_item(name=entry,
                                    href=img_href,
                                    thumbnail_href=thumb_href))
                
        up_href = None
        if self.path_info:
            up_href = self._gen_url(os.path.dirname(self.path_info),
                                    self.cgi_vars)

        subdirs.reverse() ### TODO :  Custom sort
        
        # -----------------------------------------------------------------
        # Generate the output.
        # -----------------------------------------------------------------
        
        data = self._init_template_data(1)
        data.update({
            'settings' : self._get_settings(),
            'settings_form_href' : self._gen_url(self.path_info, {}),
            'up_href' : up_href,
            'subdirs' : subdirs,
            'images' : images,
            'thumbnails' : ezt.boolean(self.cgi_vars.get('t', 'on') == 'on'),
            })
        self._generate_output(data,
                              ['Set-cookie: %s'
                               % (_cookie_string(self.cgi_vars))])

    def do_album_listing(self):
        subdirs = []
        albums = self.config.get_albums()
        albums.sort()
        for album in albums:
            options = self.config.get_album_options(album)
            if options.obscure != 0:
                continue
            subdir = _item(name=album,
                           href=self._gen_url(album, self.cgi_vars))
            subdirs.append(subdir)

        if not subdirs:
            raise MissingAlbumException
        
        data = self._init_template_data(1)
        data.update({
            'settings' : self._get_settings(),
            'settings_form_href' : self._gen_url(self.path_info, {}),
            'up_href' : None,
            'subdirs' : subdirs,
            'images' : [],
            'thumbnails' : ezt.boolean(self.cgi_vars.get('t', 'on') == 'on'),
            })
        self._generate_output(data,
                              ['Set-cookie: %s'
                               % (_cookie_string(self.cgi_vars))])
        

class _item:
  def __init__(self, **kw):
    vars(self).update(kw)


def test(path_info, query_string):
    os.environ['SCRIPT_NAME'] = '/SCRIPT_NAME'
    os.environ['SERVER_NAME'] = 'SERVER_NAME'
    os.environ['PATH_INFO'] = path_info
    os.environ['QUERY_STRING'] = query_string
    req = Request()


def print_exception():
    exc_type, exc, exc_tb = sys.exc_info()
    try:
        import traceback
        tb = string.join(traceback.format_exception(exc_type, exc, exc_tb), '')
    finally:
        # Prevent circular reference. sys.exc_info documentation warns
        # "Assigning the traceback return value to a local variable in
        # a function that is handling an exception will cause a
        # circular reference..."  This is all based on 'exc_tb', and
        # we're now done with it. Toss it.
        del exc_tb
    print 'Content-type: text/html\n'
    print '<p>'
    print '<pre style="color: blue">HTTP_COOKIE = %s</pre>' \
          % (os.environ.get('HTTP_COOKIE'))
    print '<pre style="color: green">PATH_INFO = %s</pre>' \
          % (os.environ.get('PATH_INFO'))
    print '<pre style="color: orange">QUERY_STRING = %s</pre>' \
          % (os.environ.get('QUERY_STRING'))
    print '<pre style="color: red">%s</pre>' % (tb)
    print '</p>'

    
def main():
    try:
        req = Request()
    except SystemExit:
        pass
    except MissingAlbumException:
        print 'Content-type: text/html\n'
        print '<h1>Missing Album</h1>'
        print '<p>Unable to determine which album you wish to view.</p>'
    except UnknownAlbumException, e:
        print 'Content-type: text/html\n'
        print '<h1>Unknown Album</h1>'
        print '<p>There is no album named "%s" available for viewing.</p>' \
              % (e)
    except Exception:
        print_exception()


if __name__ == "__main__":
    if os.environ.has_key('DEBUG'):
        test(sys.argv[1], sys.argv[2])
    else:
        main()
