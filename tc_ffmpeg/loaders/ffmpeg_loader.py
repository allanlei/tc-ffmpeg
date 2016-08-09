# -*- coding: utf-8 -*-
import datetime
import re
import shlex
import functools
import urlparse

import tornado.httpclient

from thumbor.loaders import LoaderResult
# from thumbor.utils import logger

from tornado.concurrent import return_future
from tornado import process

from thumbor.loaders.http_loader import quote_url


import logging
logger = logging.getLogger('tc_ffmpeg')


def _normalize_url(url, default_scheme='http'):
    # url = quote_url(url)
    parsed = urlparse.urlparse(url)
    if not parsed.scheme:
        url = default_scheme + '://' + url
    return url


def validate(context, url, normalize_url_func=_normalize_url):
    url = normalize_url_func(url)
    res = urlparse.urlparse(url)

    if not res.hostname:
        return False
    if not context.config.ALLOWED_SOURCES:
        return True

    for pattern in context.config.ALLOWED_SOURCES:
        if isinstance(pattern, re._pattern_type):
            match = url
        else:
            pattern = '^%s$' % pattern
            match = res.hostname

        if re.match(pattern, match):
            return True

    # if res.scheme not in {'http', 'https'}:
    #     pass
    # elif res.scheme not in {'file'}:
    #     pass
    # else:
    #     return False
    return False


    def boundingbox(width, height):
        if width is not None and height is None:
            height = '-1'
        elif width is None and height is not None:
            width = '-1'
        elif width is None and height is None:
            width = height = '-1'
        else:
            width = 'iw*min({width}/iw\,{height}/ih)'.format(width=width, height=height)
            height = 'ih*min({width}/iw\,{height}/ih)'.format(width=width, height=height)
        return '{width}:{height}'.format(width=width, height=height)


# def return_contents(response, url, callback, context, req_start=None):
#     if req_start:
#         finish = datetime.datetime.now()
#         res = urlparse(url)
#         context.metrics.timing(
#             'original_image.fetch.{0}.{1}'.format(response.code, res.netloc),
#             (finish - req_start).total_seconds() * 1000
#         )
#
#     result = LoaderResult()
#     context.metrics.incr('original_image.status.' + str(response.code))
#     if response.error:
#         result.successful = False
#         if response.code == 599:
#             # Return a Gateway Timeout status downstream if upstream times out
#             result.error = LoaderResult.ERROR_TIMEOUT
#         else:
#             result.error = LoaderResult.ERROR_NOT_FOUND
#
#         logger.warn(u"ERROR retrieving image {0}: {1}".format(url, str(response.error)))
#
#     elif response.body is None or len(response.body) == 0:
#         result.successful = False
#         result.error = LoaderResult.ERROR_UPSTREAM
#
#         logger.warn(u"ERROR retrieving image {0}: Empty response.".format(url))
#     else:
#         if response.time_info:
#             for x in response.time_info:
#                 context.metrics.timing('original_image.time_info.' + x, response.time_info[x] * 1000)
#             context.metrics.timing('original_image.time_info.bytes_per_second', len(response.body) / response.time_info['total'])
#         result.buffer = response.body
#         context.metrics.incr('original_image.response_bytes', len(response.body))
#
#     callback(result)


def return_contents(data, callback, *args, **kwargs):
    if not data:
        return
    result = LoaderResult(
        buffer=data,
        successful=True,
        metadata={
            'size': len(data),
            # 'updated_at': datetime.datetime.utcfromtimestamp(stats.st_mtime),
        },
    )
    callback(result)


def return_contents_error(data, callback, *args, **kwargs):
    if not data:
        return
    data = data.split('\n')[0]
    logger.error(data)

    result = LoaderResult()
    result.successful = False
    if 'Failed to resolve hostname' in data:
        result.error = LoaderResult.ERROR_UPSTREAM
    elif 'Failed to resolve hostname' in data:
        result.error = LoaderResult.ERROR_TIMEOUT
    else:
        result.error = LoaderResult.ERROR_NOT_FOUND
    callback(result)


def r(returncode, context, url, callback, req_start, process, *args, **kwargs):
    # if req_start:
    #     finish = datetime.datetime.now()
    #     res = urlparse.urlparse(url)
    #     context.metrics.timing(
    #         'original_image.fetch.{0}.{1}'.format(response.code, res.netloc),
    #         (finish - req_start).total_seconds() * 1000
    #     )
    # context.metrics.incr('original_image.status.' + str(response.code))

    if returncode > 0:
        process.stderr.read_until_close(
            callback=functools.partial(
                return_contents_error, callback=callback))
        return
    process.stdout.read_until_close(
        callback=functools.partial(
            return_contents, callback=callback))


@return_future
def load(context, url, callback, normalize_url_func=_normalize_url):
    url = normalize_url_func(url)

    options = None
    parsed = urlparse.urlparse(url)
    if parsed.scheme in ['http', 'https']:
        user_agent = None
        if context.config.HTTP_LOADER_FORWARD_USER_AGENT:
            if 'User-Agent' in context.request_handler.request.headers:
                user_agent = context.request_handler.request.headers['User-Agent']
        if user_agent is None:
            user_agent = context.config.HTTP_LOADER_DEFAULT_USER_AGENT
        using_proxy = context.config.HTTP_LOADER_PROXY_HOST and context.config.HTTP_LOADER_PROXY_PORT

        options = '-user_agent "{user_agent}" -timeout {timeout} {http_proxy}'.format(
            user_agent=user_agent,
            timeout=context.config.HTTP_LOADER_CONNECT_TIMEOUT * 1000000,
            http_proxy='-http_proxy {}'.format(using_proxy) if using_proxy else '',
        )

    command = '{bin} -loglevel error {options} -i "{uri}" -frames:v 1 -filter:v "fps=fps=1,thumbnail={scantime},scale={scale}" -map_metadata -1 -c:v {format} -f image2pipe pipe:1'.format(
        bin=context.config.FFMPEG_PATH,
        uri=url,
        format='mjpeg',
        scantime=3,
        scale=boundingbox(context.config.MAX_WIDTH or None, context.config.MAX_HEIGHT or None),
        options=options,
    )

    logger.debug('Executing: {}'.format(command))
    proc = process.Subprocess(
        shlex.split(command),
        stdout=tornado.process.Subprocess.STREAM,
        stderr=tornado.process.Subprocess.STREAM,
    )
    # proc.set_exit_callback(functools.partial(
    #     r, process=proc, context=context, url=url, callback=callback, req_start=datetime.datetime.now(),
    # ))
    proc.stdout.read_until_close(
        callback=functools.partial(return_contents, callback=callback, process=proc))
    proc.stderr.read_until_close(
        callback=functools.partial(return_contents_error, callback=callback, process=proc))
