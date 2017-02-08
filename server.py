import json
import aiohttp
import hashlib
import pickle
import asyncio
from aiohttp import web
from aiohttp.web import Response

class FlockService:
    def __init__(self):
        self.user_id2token = {}
        try:
            # Reading user_id to token mapping from local file
            self.user_id2token = pickle.load(open('user_id2token.p', 'rb'))
        except:
            pass

    @asyncio.coroutine
    def install_api(self, request):
        r = yield from request.json()
        if r['name'] == 'app.install':
            self.user_id2token[r['userId']] = r['token']
        #Saving user_id to token mapping to local file
        pickle.dump(self.user_id2token, open('user_id2token.p', 'wb'))
        return Response(status=200)

    @asyncio.coroutine
    def render_reply_box(self, request):
        event_details = json.loads(request.GET['flockEvent'])
        msg_from = event_details['userId']
        msg_to = event_details.get('chat', event_details.get('_peerId', ''))
        elem_width="60"
        elem_left = "25"
        try:
            msg_to_fetch = event_details['messageUids']['messageUid']
        except:
            # Need to display message on Mobile App
            msg_to_fetch = event_details['_messageUids'][0]
            elem_width="90"
            elem_left = "5"

        msg_details = yield from aiohttp.request("get", url="https://api.flock.co/v1/chat.fetchMessages",
            params={"token": self.user_id2token[msg_from], "chat": msg_to, "uids": [msg_to_fetch]})
        msg_details = yield from msg_details.json()
        target_user_id = msg_details[0]["from"]
        msg_text = msg_details[0]["text"][:100].replace('\n', '. ')
        if len(msg_text) > 90:
            msg_text += "..."

        profile_details = yield from aiohttp.request("get", url="https://api.flock.co/v1/users.getPublicProfile",
            params={"token": self.user_id2token[msg_from], "userId":target_user_id})
        profile_details = yield from profile_details.json()
        profile_image = profile_details['profileImage']
        first_name, last_name = profile_details['firstName'], profile_details['lastName']
        random_color = hashlib.md5((first_name+last_name).encode()).hexdigest()[-3:]
        if int(random_color, 16) < 2048:
            random_color = hex(int(random_color, 16) + 2048)[-3:]

        # Handling image attachments
        try:
            image_url = msg_details[0]["attachments"][0]["views"]["image"]["original"]["src"]
            msg_attachment = '<image id="att_img" src="{image_url}" style="max-width:200px;max-height:100px;"/>'.format(image_url=image_url)
            attachment = """ "views": {{
            "image": {{"original": {{
                    "width": document.getElementById('att_img').width, "src": "{image_url}",
                    "height": document.getElementById('att_img').height
                }}  }} }} """.format(image_url=image_url, target_user_id=target_user_id,
                    first_name=first_name, last_name=last_name)
        except:
            msg_attachment = ""
            attachment = """
            "views": {{
            "flockml": "<flockml><user userId='{target_user_id}'><b>{first_name} {last_name}</b></user></flockml>"
            }}
            """.format(target_user_id=target_user_id, first_name=first_name, last_name=last_name)



        ret = """
        <html>
        <head><script src="https://apps-static.flock.co/js-sdk/0.1.0/flock.js"></script></head>
        <body style="background-color:#f6f6f6;font:normal 13px Lucida Grande,Arial,sans-serif">
        <div style="width:{elem_width}%;left:{elem_left}%;position:absolute;top:25%;">
        <h1 style="font-size:1.5em;margin:0 0;">Replying To</h1><br>
        <div style="display:flex;clear:both;"><image style="height:34px;width:34px;margin:1px;border-radius:3px;" src="{profile_image}"></image>
        <div style=""><div style="font-weight:600;padding:0 10px 0 10px;">{first_name} {last_name}</div>
        <div style="padding:0 0 0 10px;">{msg_text}{msg_attachment}</div>
        </div><br></div>
        <textarea id="reply" style="width:100%;margin:10px 0px;height:100px;border:none;font-size:15px;border-top:1px solid #aaa;padding:14px 40px 0 8px;"></textarea><br>
        <div style="float:right">
        <button style="background: #696969;padding: 10px 25px;border: 1px solid #d1d1d1;color: #fff;cursor: pointer;border-radius: 4px;outline: none;" onclick="flock.close()">Cancel</button>
        <button style="background: #0abe51;padding: 10px 25px;border: 1px solid #0abe51;color: #fff;cursor: pointer;border-radius: 4px;outline: none;" onclick="send_reply()">Reply</button>
        </div></body><script>
            function send_reply(){{
                var xmlHttp = new XMLHttpRequest();
                xmlHttp.open("POST", "/post_to_group", false);
                var data = {{"text": document.getElementById("reply").value,
                "from": "{msg_from}",
                "to": "{msg_to}",
                "token": "{token}",
                "attachments": [{{
                    "title": "{first_name} {last_name}",
                    "description": "{msg_text}",
                    "color": "#{color}",
                    {attachment}
                }}
                ]
                }};
                xmlHttp.send(JSON.stringify(data));
                flock.close();
            }}
        </script></html>
        """.format(profile_image=profile_image, first_name=first_name, last_name=last_name,
            msg_text=msg_text, msg_from=msg_from, msg_to=msg_to, token=self.user_id2token[msg_from],
            elem_width=elem_width, elem_left=elem_left, msg_attachment=msg_attachment, attachment=attachment,
            color=random_color)

        return Response(status=200, body=ret.encode())

    @asyncio.coroutine
    def post_to_group(self, request):
        r = yield from request.json()
        resp = yield from aiohttp.request('post', url='https://api.flock.co/v1/chat.sendMessage',
            data=json.dumps(r))
        resp = yield from resp.json()
        return Response(status=200)

    @asyncio.coroutine
    def get_file(self, request):
        req = request.match_info.get('req')
        try:
            f = open(req, 'r')
            resp = f.read()
            f.close()
        except:
            resp = ''
        return Response(status=200, body=resp.encode())


app = web.Application()
loop = asyncio.get_event_loop()
http_service = FlockService()
app.router.add_route('POST', '/install', http_service.install_api)
app.router.add_route('GET', '/reply', http_service.render_reply_box)
app.router.add_route('POST', '/post_to_group', http_service.post_to_group)
app.router.add_route('POST', '/{req}', http_service.get_file)

serve = loop.create_server(app.make_handler(), '0.0.0.0', 8000)
loop.run_until_complete(serve)

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
