TITLE = 'Logo TV'
PREFIX = '/video/logotv'
ART = 'art-default.jpg'
ICON = 'icon-default.png'

BASE_URL = 'http://www.logotv.com'
RE_MANIFEST_URL = Regex('var triforceManifestURL = "(.+?)";', Regex.DOTALL)
RE_MANIFEST_FEED = Regex('var triforceManifestFeed = (.+?)}};', Regex.DOTALL)
MOSTVIEWED = BASE_URL + '/feeds/ent_m177_logo/V1_0_2/db369f93-463b-4181-b1ef-9bcb9ef6b781'

ENT_LIST = ['ent_m100', 'ent_m150', 'ent_m151', 'ent_m112', 'ent_m116']
####################################################################################################
# Set up containers for all possible objects
def Start():

    ObjectContainer.title1 = TITLE
    ObjectContainer.art = R(ART)

    DirectoryObject.thumb = R(ICON)
    EpisodeObject.thumb = R(ICON)
    VideoClipObject.thumb = R(ICON)

    HTTP.CacheTime = CACHE_1HOUR 
    HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
 
#####################################################################################
@handler(PREFIX, TITLE, art=ART, thumb=ICON)
def MainMenu():
    oc = ObjectContainer()
    oc.add(DirectoryObject(key=Callback(FeedMenu, title='Shows', url=BASE_URL+'/shows'), title='Shows'))
    oc.add(DirectoryObject(key=Callback(FeedMenu, title='Full Episodes', url=BASE_URL+'/full-episodes'), title='Full Episodes'))
    oc.add(DirectoryObject(key=Callback(ShowVideos, title='Most Viewed Videos', url=MOSTVIEWED), title='Most Viewed Videos'))
    return oc
####################################################################################################
# This function pulls the various json feeds for video sections of a page 
# Used for Shows and Full Episode main pages since this channel requires a separate function for individual shows
@route(PREFIX + '/feedmenu')
def FeedMenu(title, url, thumb=''):
    
    oc = ObjectContainer(title2=title)
    feed_title = title
    feed_list = GetFeedList(url)
    if feed_list<1:
        return ObjectContainer(header="Incompatible", message="Unable to find video feeds for %s." %url)
    
    for json_feed in feed_list:
        # Split feed to get ent code
        try: ent_code = json_feed.split('/feeds/')[1].split('_logo')[0]
        except: ent_code = ''
        if ent_code not in ENT_LIST:
            continue
        json = JSON.ObjectFromURL(json_feed, cacheTime = CACHE_1DAY)
        try: title = json['result']['promo']['headline'].title()
        except: title = feed_title
        # Create menu for the ent_m151 - full episodes to produce videos and menu items for full episode feeds by show
        if ent_code=='ent_m151':
            oc.add(DirectoryObject(key=Callback(ShowVideos, title=title, url=json_feed),
                title=title,
                thumb=Resource.ContentsOfURLWithFallback(url=thumb)
            ))
            for item in json['result']['shows']:
                oc.add(DirectoryObject(key=Callback(ShowVideos, title=item['title'], url=item['url']),
                    title=item['title']
                ))
        # Create menu items for those that need to go to Produce Sections
        # ent_m100-featured show and ent_m150-all shows
        else:
            oc.add(DirectoryObject(key=Callback(ProduceSection, title=title, url=json_feed, result_type='shows'),
                title=title,
                thumb=Resource.ContentsOfURLWithFallback(url=thumb)
            ))
            
    if len(oc) < 1:
        return ObjectContainer(header="Empty", message="There are no results to list.")
    else:
        return oc
#######################################################################################
# This function produces a list of feeds for the video sections for an individual shows
# Since the show main pages for these sites do not include json feeds that list all the full episodes or video clips,  
# we have to pull the show navigation feed, to get the video section URLs and then get the json feeds for those URLs
@route(PREFIX + '/showsections')
def ShowSections(title, url, thumb=''):
    
    oc = ObjectContainer(title2=title)
    try: content = HTTP.Request(url, cacheTime=CACHE_1DAY).content
    except: return ObjectContainer(header="Incompatible", message="This is an invalid %s." %url)
    # In case there is an issue with the manifest URL, we then try just pulling the data
    try: pagenav_feed = JSON.ObjectFromURL(RE_MANIFEST_URL.search(content).group(1))['manifest']['zones']['header']['feed']
    except: 
        try: pagenav_feed = JSON.ObjectFromString(RE_MANIFEST_FEED.search(content).group(1)+'}}')['manifest']['zones']['header']['feed']
        except: return ObjectContainer(header="Incompatible", message="Unable to find video feeds for %s." %url)
        
    if not thumb:
        try: thumb = HTML.ElementFromString(content).xpath('//meta[@property="og:image"]/@content')[0].strip()
        except: thumb = ''

    json = JSON.ObjectFromURL(pagenav_feed, cacheTime = CACHE_1DAY)
    nav_list = json['result']['showNavigation']
    
    # Get the full episode and video clip feeds 
    for section in nav_list:
        if 'episode' in section or 'video' in section or 'film' in section:
            section_title = nav_list[section]['title'].title()
            section_url = nav_list[section]['url']
            if not section_url.startswith('http://'):
                section_url = BASE_URL + section_url
            feed_list = GetFeedList(section_url)
            # There should only be one feed listed for these pages
            if 'ent_m112' in feed_list[0] or 'ent_m116' in feed_list[0]:
                oc.add(DirectoryObject(
                    key=Callback(ProduceSection, title=section_title, url=feed_list[0], result_type='filters', thumb=thumb),
                    title=section_title,
                    thumb = Resource.ContentsOfURLWithFallback(url=thumb)
                ))
        # Create video object for listed special full shows
        elif 'full special' in section:
            oc.add(VideoClipObject(
                url = nav_list[section]['url'], 
                title = nav_list[section]['title'], 
                thumb = Resource.ContentsOfURLWithFallback(url=thumb)
            ))

    if len(oc) < 1:
        Log ('still no value for objects')
        return ObjectContainer(header="Empty", message="There are no video sections for this show." )
    else:
        return oc
#####################################################################################
# For Producing the sections from various json feeds
# This function can produce show lists, AtoZ show lists, and video filter lists
@route(PREFIX + '/producesections')
def ProduceSection(title, url, result_type, thumb='', alpha=''):
    
    oc = ObjectContainer(title2=title)
    (section_title, feed_url) = (title, url)
    json = JSON.ObjectFromURL(url)

    item_list = json['result'][result_type]
    # Create item list for individual sections of alphabet for the All listings
    if '/feeds/ent_m150' in feed_url and alpha:
        item_list = json['result'][result_type][alpha]
    for item in item_list:
        # Create a list of show sections
        if result_type=='shows':
            if '/feeds/ent_m150' in feed_url and not alpha:
                oc.add(DirectoryObject(
                    key=Callback(ProduceSection, title=item, url=feed_url, result_type=result_type, alpha=item),
                    title=item.replace('hash', '#').title()
                ))
            else:
                try: url = item['url']
                except: url = item['canonicalURL']
                # Skip bad show urls that do not include '/shows/' or events. If '/events/' there is no manifest.
                if '/shows/' not in url:
                    continue
                try: thumb = item['images'][0]['url']
                except: thumb = thumb
                oc.add(DirectoryObject(
                    key=Callback(ShowSections, title=item['title'], url=url, thumb=thumb),
                    title=item['title'],
                    thumb = Resource.ContentsOfURLWithFallback(url=thumb)
                ))
        # Create season sections for filters
        else:
            # Skip any empty sections
            try: count=item['subFilters'][1]['count']
            except: count=item['count']
            if  count==0:
                continue
            title=item['name']
            # Skip the All Seasons section for Full Episodes since they include episode summaries that are not videos
            if 'All Seasons' in title and 'Episode' in section_title:
                continue
            # Add All to Full Episodes section
            if 'Episode' in title:
                title='All ' +   title
            try: url=item['subFilters'][1]['url'] 
            except: url=item['url']
            oc.add(DirectoryObject(
                key=Callback(ShowVideos, title=title, url=url),
                title=title,
                thumb=Resource.ContentsOfURLWithFallback(url=thumb)
            ))
    
    if len(oc) < 1:
        Log ('still no value for objects')
        return ObjectContainer(header="Empty", message="There are no results to list right now.")
    else:
        return oc
#######################################################################################
# This function produces the videos listed in json feed under items
@route(PREFIX + '/showvideos')
def ShowVideos(title, url):

    oc = ObjectContainer(title2=title)
    json = JSON.ObjectFromURL(url)
    try: videos = json['result']['items']
    except: return ObjectContainer(header="Empty", message="There are no videos to list right now.")
    
    for video in videos:

        try: vid_url = video['canonicalURL']
        except: continue

        # catch any bad links that get sent here
        if not ('/video-clips/') in vid_url and not ('/full-episodes/') in vid_url:
            continue

        thumb = video['images'][0]['url']

        show = video['show']['title']
        try: episode = int(video['season']['episodeNumber'])
        except: episode = 0
        try: season = int(video['season']['seasonNumber'])
        except: season = 0
        
        try: unix_date = video['airDate']
        except:
            try: unix_date = video['publishDate']
            except: unix_date = unix_date = video['date']['originalPublishDate']['timestamp']
        date = Datetime.FromTimestamp(float(unix_date)).strftime('%m/%d/%Y')
        date = Datetime.ParseDate(date)

        # Durations for clips have decimal points
        duration = video['duration']
        if not isinstance(duration, int):
            duration = int(duration.split('.')[0])
        duration = duration * 1000

        # Everything else has episode and show info now
        oc.add(EpisodeObject(
            url = vid_url, 
            show = show,
            season = season,
            index = episode,
            title = video['title'], 
            thumb = Resource.ContentsOfURLWithFallback(url=thumb ),
            originally_available_at = date,
            duration = duration,
            summary = video['description']
        ))

    try: next_page = json['result']['nextPageURL']
    except: next_page = None

    if next_page and len(oc) > 0:

        oc.add(NextPageObject(
            key = Callback(ShowVideos, title=title, url=next_page),
            title = 'Next Page ...'
        ))

    if len(oc) < 1:
        Log ('still no value for objects')
        return ObjectContainer(header="Empty", message="There are no unlocked videos available to watch.")
    else:
        return oc
####################################################################################################
# This function pulls the list of json feeds from a manifest
@route(PREFIX + '/getfeedlist')
def GetFeedList(url):
    
    feed_list = []
    # In case there is an issue with the manifest URL, we then try just pulling the manifest data
    try: content = HTTP.Request(url, cacheTime=CACHE_1DAY).content
    except: content = ''
    try: zone_list = JSON.ObjectFromURL(RE_MANIFEST_URL.search(content).group(1))['manifest']['zones']
    except:
        try: zone_list = JSON.ObjectFromString(RE_MANIFEST_FEED.search(content).group(1)+'}}')['manifest']['zones']
        except: zone_list = []
    
    for zone in zone_list:
        if zone in ('header', 'footer', 'ads-reporting', 'ENT_M171'):
            continue
        json_feed = zone_list[zone]['feed']
        #Log('the value of json_feed is %s' %json_feed)
        feed_list.append(json_feed)

    return feed_list
