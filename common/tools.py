import re
import os
from PIL import Image
from zipfile import ZipFile


def format_cookie(oringal_cookies: str) -> dict:
    cookies = {}
    for cookie in oringal_cookies.split(";"):
        key, value = cookie.split("=", 1)
        key = re.sub(" ", "", key)
        value = re.sub(" ", "", value)
        cookies[key] = value
    return {"PHPSESSID": cookies.get("PHPSESSID")}


def compare_datetime(lasttime: str, newtime: str) -> bool:
    time1 = [lasttime[0:4], lasttime[4:6], lasttime[6:8]]
    time2 = [newtime[0:4], newtime[4:6], newtime[6:8]]
    # print(time1,time2)
    if time2[0] > time1[0]:
        return True
    elif time2[0] == time1[0]:
        if time2[1] > time1[1]:
            return True
        elif time2[1] == time1[1]:
            return time2[2] > time1[2]
    return False


def make_gif(zip_path: str, image_dir, save_path: str, frames: list) -> bool:
    # 解压zip
    with ZipFile(zip_path, "r") as f:
        f.extractall(image_dir)
    # 删除临时zip文件
    os.remove(zip_path)
    # 创建GIF动图
    image_list = []
    duration = []
    for frame in frames:
        image = Image.open(image_dir + frame.get("file"))
        image_list.append(image)
        duration.append(frame.get("delay"))
    image_list[0].save(
        save_path,
        save_all=True,
        append_images=image_list[1:],
        optimize=False,
        duration=duration,
        loop=0,
    )
    # 删除解压图片文件夹
    for file_name in os.listdir(image_dir):
        tf = os.path.join(image_dir, file_name)
        os.remove(tf)
    os.rmdir(image_dir)
    return True


def check_image(path: str) -> bool:
    if os.path.exists(path):
        """
        with open(image_path, 'rb') as f:
            buf = f.read()
            if buf[6:10] in (b'JFIF', b'Exif'):     # jpg图片
                if not buf.rstrip(b'\0\r\n').endswith(b'\xff\xd9'):
                    bValid = False
            else:
                try:
                    Image.open(f).verify()
                except Exception:
                    bValid = False
        """
        with open(path, "rb") as f:
            try:
                # Image.open(f).verify()
                image = Image.open(f)
                # 若图片大部分为灰
                valid_1 = image.getpixel((image.width - 1, image.height - 1)) == (
                    128,
                    128,
                    128,
                )
                valid_2 = image.getpixel((int(image.width / 2), image.height - 1)) == (
                    128,
                    128,
                    128,
                )
                valid_3 = image.getpixel((0, image.height - 1)) == (128, 128, 128)
                if valid_1 and valid_2 and valid_3:
                    return False
                else:
                    return True
            except OSError:
                return False
            except Exception:
                return False
    else:
        return False


# print(check_image('C:/Users/Administrator/Desktop/120205761_p0.jpg'))
# work_type = "manga"
# print((work_type == "illust") or (work_type == "manga"))
"""
import httpx
    from parsel import Selector

    login_url = "https://accounts.pixiv.net/ajax/login"
    payload = {
        "login_id": "pweb2@tutamail.com",
        "password": "pixiv_webcrawler",
        "source":"pc",
        "app_ios":0,
        "ref":"",
        "return_to":"https://www.pixiv.net/en/",
        "g_recaptcha_response":"",
        "recaptcha_enterprise_score_token":"",
    }
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")

    # 用 Client 会自动在后续请求里携带 Cookie；follow_redirects=True 避免 30x 丢掉 Set-Cookie
    with httpx.Client(headers={"User-Agent": UA, "Referer": "https://accounts.pixiv.net/"},follow_redirects=True) as client:
        # ① 取 post_key
        login_page = client.get("https://accounts.pixiv.net/login")
        login_page.raise_for_status()
        sel = Selector(login_page.text)
        post_key = sel.css('#init-config').re(r'(?<="pixivAccount.tt":").{32}')[0]
        print(post_key)
        payload.update({"tt":post_key})
        resp = client.post(login_url, data=payload)
        print(resp.json())

        # 打印所有 Set-Cookie 行
        for cookie_line in resp.headers.get_list("set-cookie"):
            print(cookie_line)

        # 如果想看解析后的 Cookie 键值对：
        print("--- parsed cookies ---")
        for name, value in resp.cookies.items():
            print(f"{name} = {value}")
"""