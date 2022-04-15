from so_ana.infrastructure.error_handling import ExceptionInfo, get_traceback


def with_forward_error_func(func):
    """
    Decorator to wrap flow task with generic error handler
    :param func: function to be decorated
    :return: decorated function
    """

    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            return ExceptionInfo(exc_type='FlowTaskError',
                                 exc_args=get_traceback(exc),
                                 exc_details=ExceptionInfo.from_exception(exc)
                                 )
    return wrapped