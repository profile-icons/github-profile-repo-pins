from gh_profile_repo_pins.repo_pins_exceptions import RepoPinImageMediaError
import gh_profile_repo_pins.repo_pins_enum as enums
from gh_profile_repo_pins.utils import load_img
from PIL import Image as im, ImageOps as im_ops
from requests import get, Response, HTTPError
from urllib.parse import urlparse
from base64 import b64encode
from cairosvg import svg2png
from io import BytesIO


class RepoPinImgMedia:

    __DEFAULT_ALIGN: str = "xMidYMid"
    __DEFAULT_MODE: str = "stretch"
    __DEFAULT_OPACITY: float = 0.25

    __BASE_64_ENCODING: str = "ascii"
    __RES_MIME_HEADER: str = "Content-Type"
    __IMG_DIMS: int = 1600
    __IMG_QUALITY: int = 80
    __IMG_COMPRESSION: int = 6

    def __init__(
        self,
        img: str | None = None,
        align: str = __DEFAULT_ALIGN,
        mode: str = __DEFAULT_MODE,
        opacity: float = __DEFAULT_OPACITY,
    ) -> None:
        assert img
        self.__img = img
        self.__img_mime: enums.RepoPinsImgMediaImgMime = (
            enums.RepoPinsImgMediaImgMime.PNG
        )
        self.__img_align: enums.RepoPinsImgMediaImgAlign = (
            enums.RepoPinsImgMediaImgAlign(align.lower())
            if align and align.lower() in enums.RepoPinsImgMediaImgAlign
            else enums.RepoPinsImgMediaImgAlign(self.__DEFAULT_ALIGN.lower())
        )
        self.__img_mode: enums.RepoPinsImgMediaImgMode = (
            enums.RepoPinsImgMediaImgMode(mode.lower())
            if mode
            else enums.RepoPinsImgMediaImgMode(self.__DEFAULT_MODE.lower())
        )
        self.__img_opacity: float | int = (
            opacity
            if opacity is not None and 0.0 <= opacity <= 1.0
            else self.__DEFAULT_OPACITY
        )
        self.__img_encoded_url: str | None = None

    def __repr__(self) -> str:
        return (
            f"{enums.RepoPinsResDictKeys.IMG.value}: {self.__img}\n"
            f"align: {self.__img_align}\n"
            f"mode: {self.__img_mode}\n"
            f"opacity: {self.__img_opacity}\n"
            f"encoded URL: {self.__img_encoded_url}\n"
        )

    def __is_img_url(self) -> bool:
        return bool(urlparse(url=self.__img).scheme)

    def __decode_img(self, byte_img: bytes) -> im.Image:
        if self.__img_mime == enums.RepoPinsImgMediaImgMime.SVG:
            raw_conversion: BytesIO = BytesIO()
            svg2png(bytestring=byte_img, write_to=raw_conversion)
            raw_conversion.seek(0)
            return im.open(fp=raw_conversion)
        return im.open(fp=BytesIO(initial_bytes=byte_img))

    def __format_encoded_img(self, byte_img: bytes) -> bytes:
        img_encoder: im.Image = im_ops.exif_transpose(
            image=self.__decode_img(byte_img=byte_img)
        )
        img_encoder.thumbnail(size=(self.__IMG_DIMS, self.__IMG_DIMS))

        self.__img_mime = enums.RepoPinsImgMediaImgMime.WEB
        encoded_img: BytesIO = BytesIO()
        img_encoder.save(
            fp=encoded_img,
            format=self.__img_mime.value.split("/")[-1].upper(),
            quality=self.__IMG_QUALITY,
            method=self.__IMG_COMPRESSION,
        )
        return encoded_img.getvalue()

    def __set_encoded_url(self, encoded_url: str) -> None:
        self.__img_encoded_url = (
            f"data:{self.__img_mime.value.lower()};base64,{encoded_url}"
        )

    def __load_url(self) -> None:
        try:
            res: Response = get(url=self.__img, timeout=5)
            res.raise_for_status()
        except HTTPError:
            raise RepoPinImageMediaError(
                msg=f"HTTPError attempting to fetch image URL: {self.__img}."
            )
        self.__img_mime = enums.RepoPinsImgMediaImgMime(
            res.headers.get(self.__RES_MIME_HEADER, self.__img_mime.value).lower()
        )
        self.__set_encoded_url(
            encoded_url=b64encode(
                s=self.__format_encoded_img(byte_img=res.content)
            ).decode(encoding=self.__BASE_64_ENCODING)
        )

    def __load_file(self) -> None:
        try:
            self.__img_mime = enums.RepoPinsImgMediaImgMime(
                [
                    e.value
                    for e in enums.RepoPinsImgMediaImgMime
                    if self.__img.split(".")[-1][:2].upper() == e.name[:2]
                ][0]
            )
        except IndexError:
            raise RepoPinImageMediaError(
                msg=f"Invalid image type. "
                f"Use one of the valid types: {list(enums.RepoPinsImgMediaImgMime.__members__.keys())}."
            )

        try:
            self.__img = load_img(img_path=self.__img)
        except FileNotFoundError:
            raise RepoPinImageMediaError(msg=f"Image file not found: {self.__img}")
        self.__set_encoded_url(
            encoded_url=b64encode(
                s=self.__format_encoded_img(byte_img=self.__img)
            ).decode(encoding=self.__BASE_64_ENCODING)
        )

    @property
    def align(self) -> enums.RepoPinsImgMediaImgAlign:
        return self.__img_align

    @property
    def mode(self) -> enums.RepoPinsImgMediaImgMode:
        return self.__img_mode

    @property
    def opacity(self) -> float | int:
        return self.__img_opacity

    @property
    def encoded_url(self) -> str | None:
        return self.__img_encoded_url

    def load(self) -> None:
        if self.__img:
            if self.__is_img_url():
                self.__load_url()
            elif self.__img.startswith("data:"):
                self.__img_encoded_url = self.__img
            else:
                self.__load_file()
