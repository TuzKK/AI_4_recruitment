"""Stop a batch promptly when the provider reports an account billing block."""
import threading
import httpx

API_ABORT=threading.Event()


class AccountBlocked(RuntimeError):
    pass


def guard_model(model):
    original=model._ask
    def ask(system,user):
        if API_ABORT.is_set():
            raise AccountBlocked('Arrearage: batch stopped; restore account before restarting')
        try:
            return original(system,user)
        except httpx.HTTPStatusError as exc:
            try:
                error=exc.response.json().get('error',{})
            except (ValueError,AttributeError):
                error={}
            if isinstance(error,dict) and error.get('code')=='Arrearage':
                API_ABORT.set()
                raise AccountBlocked('Arrearage: provider denied access because of account billing status') from None
            raise
    model._ask=ask
    return model
