"""Generate the donation QR asset and verify its payload with an independent decoder.

Requires requirements-build.txt. No QR packages are needed to run OpenLUFS.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import qrcode
import zxingcpp
from PIL import Image
from openlufs.about_dialog import DONATION_BTC_ADDRESS,DONATION_BTC_URI


def generate():
    destination=ROOT/"assets/donation-btc-qr.png"
    qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q,box_size=10,border=4)
    qr.add_data(DONATION_BTC_URI);qr.make(fit=True)
    # Opaque black-on-white modules and a four-module quiet zone maximize readability.
    image=qr.make_image(fill_color="black",back_color="white").convert("RGB")
    image.save(destination)
    decoded=zxingcpp.read_barcode(Image.open(destination))
    if decoded is None or decoded.text!=DONATION_BTC_URI:
        raise RuntimeError("Donation QR code did not decode to the exact owner address.")
    # Also verify the 205-pixel presentation used in the application.
    displayed=image.resize((205,205),Image.Resampling.NEAREST)
    decoded=zxingcpp.read_barcode(displayed)
    if decoded is None or decoded.text!="bitcoin:"+DONATION_BTC_ADDRESS:
        raise RuntimeError("Displayed donation QR did not decode correctly.")
    print("Verified donation QR:",DONATION_BTC_URI)


if __name__=="__main__":generate()
