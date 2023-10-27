import json

"""Partially derived from OpenAI's python library errors."""


class GptmodError(Exception):
    def __init__(
        self,
        message=None,
        json_body=None,
        request=None,
        code=None,
    ):
        super(GptmodError, self).__init__(message)

        self._message = message
        self.json_body = json_body or {}
        self.request = request or {}
        if "key" in self.request:
            self.request.pop("key")
        self.code = code
        if isinstance(self.json_body, dict):
            if "code" in self.json_body:
                self.code = code

    def __str__(self):
        return (
            "%s(message=%r, request=%r, json=%r)"
            % (self.__class__.__name__, self._message, self.request, self.json_body)
        )[:1024]

    @property
    def user_message(self):
        return self._message

    def __repr__(self):
        return "%s(message=%r, request=%r, json=%r)" % (
            self.__class__.__name__,
            self._message,
            self.request,
            self.json_body,
        )


class KeyException(GptmodError):
    def __init__(self, message):
        self._message = message or "API KEY HAS NOT BEEN SET!"
        super(KeyException, self).__init__(self._message)


class Timeout(GptmodError):
    def __init__(self, message):
        self._message = message or "REQUEST TIMED OUT!"
        super(Timeout, self).__init__(self._message)


class APIConnectionError(GptmodError):
    pass
