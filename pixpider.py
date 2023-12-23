import re
from datetime import datetime
from enum import Enum
from math import isqrt
from typing import Literal, cast

import requests
import streamlit as st
from pytz import timezone
from pydantic import BaseModel
from pydantic.alias_generators import to_camel
from streamlit import session_state as state
from streamlit.delta_generator import DeltaGenerator
from streamlit_tags import st_tags


api_url = 'https://api.lolicon.app/setu/v2'
url_maps = {
    'direct': 'https://pixiv.re/{pid}-{p+1}.{ext}',
    'original': 'https://{proxy}/img-original/img/{date}/{pid}_p{p}.{ext}',
    'regular': 'https://{proxy}/img-master/img/{date}/{pid}_p{p}_master1200.{ext}',
    'small': 'https://{proxy}/c/540x540_70/img-master/img/{date}/{pid}_p{p}_master1200.{ext}',
    'thumb': 'https://{proxy}/c/250x250_80_a2/img-master/img/{date}/{pid}_p{p}_master1200.{ext}',
    'mini': 'https://{proxy}/c/250x250_80_a2/img-master/img/{date}/{pid}_p{p}_master1200.{ext}',
}
r18_options = 'False', 'True', 'Both'
size_options = 'direct', 'original', 'regular', 'small', 'thumb', 'mini'
if 'date_range' not in state:
    state['date_range'] = datetime(2007, 9, 10), datetime.today()
if 'timezone' not in state:
    state['timezone'] = timezone('Japan')


class AiType(Enum):
    Unknown = 0
    No = 1
    Yes = 2


class Picture(BaseModel, alias_generator=to_camel):
    pid: int
    p: int
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
        self.upload_date = self.upload_date.astimezone(state['timezone'])

    def bind(self, dg: DeltaGenerator) -> None:
        self._dg = dg
        self.update()

    def update(self) -> None:
        with self._dg.container(border=True):
            data = self.model_dump(by_alias=True)
            data['aiType'] = cast(AiType, data['aiType']).name.lower()
            data['uploadDate'] = cast(datetime, data['uploadDate']).isoformat()
            data['url'] = self.url
            st.expander('details').json(data)
            if self.p_count == 1:
                st.image(self.url, caption=self.caption)
                return
            tabs = st.tabs([f'p{p+1}' for p in range(self.p_count)])
            for p in range(self.p_count):
                self.p = p
                tabs[p].image(self.url, caption=self.caption)

    @property
    def p_count(self) -> int:
        url = f'https://pixiv.re/{self.pid}-65536.{self.ext}'
        text = requests.get(url).text
        if matched := re.search(r'This work has (\d+|just one) ', text):
            p_count = matched.group(0)[14:-1]
            return 1 if p_count == 'just one' else int(p_count)
        st.error(text)
        return -1

    @property
    def url(self) -> str:
        assert size is not None
        return url_maps[size].format(
            proxy=proxy,
            date=self.upload_date.strftime(r'%Y/%m/%d/%H/%M/%S'),
            pid=self.pid, p=self.p, ext=self.ext, **{'p+1': self.p + 1}
        ).replace('-1', '')

    @property
    def caption(self) -> str:
        return f'{self.title} by {self.author}'


st.set_page_config("PixPider", ":spider:", 'wide')
with st.sidebar:
    st.title(':spider: :rainbow[PixPider]')
    r18 = st.selectbox('r18', r18_options)
    num = st.slider('num', 1, 20, 1)
    uid = st.number_input('uid', step=1)
    keyword = st.text_input('keyword')
    tags = st_tags(label='tags', text='', key='tags')

    def no_fetch() -> None:
        state['loaded'] = True

    size = st.radio('size', size_options, on_change=no_fetch, horizontal=True)
    proxy = st.text_input('proxy', 'i.pixiv.re', disabled=size == 'direct')
    date_range = st.slider('date range', value=state['date_range'])
    date_from, date_to = cast(tuple[datetime, datetime], date_range)
    dsc_help = 'Disable replacing certain abbreviations `keywords` and `tags`'
    dsc = st.checkbox('dsc', help=dsc_help)
    excludeAI = st.checkbox('exclude AI')
    st.button('fetch', type='primary')


if 'loaded' in state:
    del state['loaded']
else:
    state['params'] = dict(
        r18=r18_options.index(r18),
        num=num,
        uid=uid,
        keyword=keyword,
        tag=tags,
        size=size_options,
        proxy=proxy,
        dateAfter=date_from.timestamp() * 1000,
        dateBefore=date_to.timestamp() * 1000,
        dsc=dsc,
        excludeAI=excludeAI,
    )
    state['response'] = requests.post(api_url, json=state['params']).json()
    if error := state['response']['error']:
        st.error(error)

pictures: list[Picture] = [Picture(**pic) for pic in state['response']['data']]
picture_counts = len(pictures)
max_columns = isqrt(picture_counts)
columns = st.columns(min(picture_counts, max_columns))
for index, picture in enumerate(pictures):
    picture.bind(columns[index % max_columns])
