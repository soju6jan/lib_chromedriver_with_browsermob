import os, sys, time, traceback, base64, requests, platform
from selenium import webdriver
from browsermobproxy import Server

class ChromeDriverWithBrowsermob:
    proxy_server = None

    def __init__(self, config):
        self.config = config
        self.logger = config['logger']
        self.driver = None
        self.proxy = None

    def init_driver(self, url=None):
        try:
            if self.driver != None:
                return self.driver

            options = webdriver.ChromeOptions()
            chrome_url = self.config.get('chrome_url')
            if chrome_url != None and chrome_url != '': # remote
                self.driver = webdriver.Remote(chrome_url, options.to_capabilities())
            else:
                options.add_argument('window-size=1920x1080')
                if platform.system() == 'Windows':
                    chromedriver = os.path.join(os.path.dirname(__file__), 'bin', 'chromedriver.exe')
                    if self.config.get('headless', False):
                        options.add_argument('headless')
                else:
                    chromedriver = 'chromedriver'
                    options.add_argument('--headless')
                    options.add_argument('--no-sandbox')
                    options.add_argument("disable-gpu")
                    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36")
                    options.add_argument("lang=ko_KR")
            tmp = self.config.get('driver_options')
            if tmp:
                for option in tmp:
                    options.add_argument(option)
            chrome_data_path = self.config.get('data_path')
            if chrome_data_path != None:
                os.makedirs(chrome_data_path, exist_ok=True)
                options.add_argument(f"user-data-dir={chrome_data_path}")

            if self.config.get('use_proxy'):
                self.__create_proxy()
                options.add_argument(f"--proxy-server={self.proxy.proxy}")
                options.add_argument('--ignore-certificate-errors')
                options.add_argument('--ignore-certificate-errors-spki-list')

            self.driver = webdriver.Chrome(chromedriver, chrome_options=options)
            if url is not None:
                self.go_reset_har(url)
        except Exception as exception: 
            self.logger.error('Exception:%s', exception)
            self.logger.error(traceback.format_exc())    
        return self.driver

    
    def __driver_stop(self):
        if self.driver is not None:
            try: self.driver.close()
            except: pass
            time.sleep(3)
            try: self.driver.quit()
            except: pass
            self.driver = None


    def __create_proxy(self):
        if self.proxy is not None:
            return
        if self.proxy_server == None:
            if platform.system() == 'Windows':
                self.proxy_server = Server(path=os.path.join(os.path.dirname(__file__), 'browsermob-proxy-2.1.4', 'bin', 'browsermob-proxy.bat'), options={'port':52100})
            else:
                self.proxy_server = Server(path=os.path.join(os.path.dirname(__file__), 'browsermob-proxy-2.1.4', 'bin', 'browsermob-proxy'), options={'port':52100})
            self.proxy_server.start()
            self.logger.debug('proxy server start!!')
            time.sleep(1)

        while True:
            try:
                self.proxy = self.proxy_server.create_proxy(params={'trustAllServers':'true'})
                break
            except Exception as exception: 
                self.logger.error('Exception:%s', exception)
                self.logger.error(traceback.format_exc())    
                time.sleep(2)
                #self.proxy = self.proxy_server.create_proxy(params={'trustAllServers':'true'})
        time.sleep(1)
        self.logger.debug('proxy : %s', self.proxy.proxy)
        #self.logger.debug('proxy : %s', self.proxy.har)
        #command = [self.chromedriver_binary, '--port=%s' % ModelSetting.get('server_port')]

    

    def proxy_stop(self):
        try:
            self.logger.error("proxy_stop")
            #self.driver_stop()
            if self.proxy_server is not None:
                try: self.proxy_server.stop()
                except Exception as e: 
                    self.logger.error('Exception:%s', e)
                    self.logger.error(traceback.format_exc())
                self.proxy_server = None
        except Exception as exception: 
            self.logger.error('Exception:%s', exception)
            self.logger.error(traceback.format_exc())    

    
    def close(self):
        self.__driver_stop()
        self.__proxy_stop()


    def go_reset_har(self, url, har_option={'captureHeaders': True, 'captureCookies':False, 'captureContent':True}):
        self.init_driver()
        if self.proxy != None:
            self.proxy.new_har(url, options=har_option)
        self.driver.get(url)

    def get_har(self):
        if self.proxy != None:
            data = self.proxy.har
            self.proxy.new_har(None)
            return data
        

    def get_file_content_chrome(self, uri):
        driver = self.driver
        result = driver.execute_async_script("""
            var uri = arguments[0];
            var callback = arguments[1];
            var toBase64 = function(buffer){for(var r,n=new Uint8Array(buffer),t=n.length,a=new Uint8Array(4*Math.ceil(t/3)),i=new Uint8Array(64),o=0,c=0;64>c;++c)i[c]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".charCodeAt(c);for(c=0;t-t%3>c;c+=3,o+=4)r=n[c]<<16|n[c+1]<<8|n[c+2],a[o]=i[r>>18],a[o+1]=i[r>>12&63],a[o+2]=i[r>>6&63],a[o+3]=i[63&r];return t%3===1?(r=n[t-1],a[o]=i[r>>2],a[o+1]=i[r<<4&63],a[o+2]=61,a[o+3]=61):t%3===2&&(r=(n[t-2]<<8)+n[t-1],a[o]=i[r>>10],a[o+1]=i[r>>4&63],a[o+2]=i[r<<2&63],a[o+3]=61),new TextDecoder("ascii").decode(a)};
            var xhr = new XMLHttpRequest();
            xhr.responseType = 'arraybuffer';
            xhr.onload = function(){ callback(toBase64(xhr.response)) };
            xhr.onerror = function(){ callback(xhr.status) };
            xhr.open('GET', uri);
            xhr.send();
            """, uri)
        if type(result) == int :
            raise Exception("Request failed with status %s" % result)
        return base64.b64decode(result)
    


    def get_response(self, item):
        try:
            headers = {}
            for h in item['request']['headers']:
                if h['name'].lower() == 'accept-encoding':
                    continue
                headers[h['name']] = h['value']
            
            if item['request']['method'] == 'GET':
                return requests.get(item['request']['url'], headers=headers)
            elif item['request']['method'] == 'POST':
                data = ''
                if item['request']['postData']['mimeType'] == 'application/json;charset=UTF-8':
                    data = item['request']['postData']['text']
                return requests.post(item['request']['url'], headers=headers, data=data)
        except Exception as e: 
            self.logger.error('Exception:%s', e)
            self.logger.error(traceback.format_exc())

    
    