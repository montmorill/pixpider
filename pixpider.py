from datetime import datetime
from enum import Enum
from functools import cached_property
from math import isqrt
from typing import Literal, cast

import requests
import streamlit as st
from pytz import timezone
from pydantic import BaseModel
from pydantic.alias_generators import to_camel
from streamlit import cache_data, session_state
from streamlit.delta_generator import DeltaGenerator
from streamlit_tags import st_tags


api_url = 'https://api.lolicon.app/setu/v2'
url_maps = {
    'original': 'https://{proxy}/img-original/img/{date}/{pid}_p{p}.{ext}',
    'regular': 'https://{proxy}/img-master/img/{date}/{pid}_p{p}_master1200.{ext}',
    'small': 'https://{proxy}/c/540x540_70/img-master/img/{date}/{pid}_p{p}_master1200.{ext}',
    'thumb': 'https://{proxy}/c/250x250_80_a2/img-master/img/{date}/{pid}_p{p}_master1200.{ext}',
    'mini': 'https://{proxy}/c/250x250_80_a2/img-master/img/{date}/{pid}_p{p}_master1200.{ext}',
}
r18_options = 'False', 'True', 'Both'
size_options = 'original', 'regular', 'small', 'thumb', 'mini'

state = cast(dict, session_state)


@cache_data
def date_range():
    return datetime(2007, 9, 10), datetime.today()


def no_fetch() -> None:
    state['loaded'] = True


class AiType(Enum):
    Unknown = 0
    No = 1
    Yes = 2


class Picture(BaseModel, alias_generator=to_camel):
    pid: int
    uid: int
    title: str
    author: str
    r18: bool
    width: int
    height: int
    tags: list[str]
    ext: Literal['jpg', 'png', 'gif']
    ai_type: AiType
    upload_date: datetime

    _dg: DeltaGenerator

    def __init__(self, **data) -> None:
        super().__init__(**data)
        self.upload_date = self.upload_date.astimezone(timezone('Japan'))

    def bind(self, dg: DeltaGenerator) -> None:
        self._dg = dg
        self.update()

    def update(self) -> None:
        with self._dg.container(border=True):
            data = self.model_dump(by_alias=True)
            data['pageCount'] = self.page_count
            data['aiType'] = cast(AiType, data['aiType']).name.lower()
            data['uploadDate'] = cast(datetime, data['uploadDate']).isoformat()
            data['urls'] = [self.url(p) for p in range(self.page_count)]
            st.expander('details').json(data)
            if self.page_count == 1:
                st.image(self.url(0), caption=self.caption)
            elif self.page_count != 0:
                tabs = st.tabs([f'p{p+1}' for p in range(self.page_count)])
                for p in range(self.page_count):
                    caption = f"{self.caption} ({p + 1}/{self.page_count})"
                    tabs[p].image(self.url(p), caption)
            else:
                st.error("Oops, we can't find the picture anywhere!")

    @cached_property
    def page_count(self) -> int:
        page_count = 0
        while requests.head(self.url(page_count)):
            page_count += 1
        return page_count

    def url(self, p: int) -> str:
        return url_maps[cast(str, size)].format(
            proxy=proxy,
            date=self.upload_date.strftime(r'%Y/%m/%d/%H/%M/%S'),
            pid=self.pid,
            p=p,
            ext=self.ext,
        )

    @cached_property
    def caption(self) -> str:
        return f'{self.title} by {self.author}'


st.set_page_config("PixPider", ":spider:", 'wide')
with st.sidebar:
    st.title(':spider: :rainbow[PixPider]')
    r18 = st.selectbox('r18', r18_options)
    num = st.slider('num', 1, 20)
    uid = st.number_input('uid', step=1)
    keyword = st.text_input('keyword')
    tags = st_tags(label='tags', text='', key='tags')
    size = st.radio('size', size_options, on_change=no_fetch, horizontal=True)
    proxy = st.text_input('proxy', 'i.pixiv.re')
    _date_range = st.slider('date range', value=date_range())
    date_from, date_to = cast(tuple[datetime, datetime], _date_range)
    left, right = st.columns(2)
    dsc_help = 'Disable replacing certain abbreviations `keywords` and `tags`'
    dsc = left.checkbox('dsc', help=dsc_help)
    exclude_ai = right.checkbox('exclude AI')
    st.button('fetch', type='primary', use_container_width=True)


if 'loaded' in state:
    del state['loaded']
else:
    state['params'] = dict(
        r18=r18_options.index(r18),
        num=num,
        uid=uid,
        keyword=keyword,
        tag=tags,
        size=size,
        proxy=proxy,
        date_after=date_from.timestamp() * 1000,
        date_before=date_to.timestamp() * 1000,
        dsc=dsc,
        exclude_ai=exclude_ai,
    )
    state['params'] = {to_camel(k): v for k, v in state['params'].items()}
    state['response'] = requests.post(api_url, json=state['params']).json()
    if error := state['response']['error']:
        st.error(error)

pictures = [Picture(**pic) for pic in state['response']['data']]
if picture_count := len(pictures):
    column_count = isqrt(picture_count)
    columns = st.columns(column_count)
    for index, picture in enumerate(pictures):
        picture.bind(columns[index % column_count])
else:
    st.error('Sorry, there are no images match the filter.')
