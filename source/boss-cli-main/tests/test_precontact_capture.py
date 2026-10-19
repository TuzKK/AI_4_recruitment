from boss_cli.precontact_capture import capture_status, evidence_key, next_scroll


def test_scroll_keeps_overlap_and_reaches_bottom():
    assert next_scroll(0, 500, 1300) == 400
    assert next_scroll(400, 500, 1300) == 800
    assert next_scroll(800, 500, 1300) == 800


def test_limits_never_claim_complete():
    assert capture_status(bottom=True, stable=3, limited=False) == "captured_unverified"
    assert capture_status(bottom=True, stable=3, limited=True) == "partial"
    assert capture_status(bottom=False, stable=3, limited=False) == "partial"


def test_candidate_path_cannot_escape_output():
    key = evidence_key("../../candidate/a")
    assert "/" not in key and "\\" not in key and ".." not in key
    assert key == evidence_key("../../candidate/a")


def test_post_capture_account_failure_downgrades_result(tmp_path):
    import base64
    import io

    from PIL import Image

    from boss_cli.precontact_capture import capture_extension
    image = io.BytesIO()
    Image.new('RGB', (10, 10), 'white').save(image, 'PNG')
    encoded = base64.b64encode(image.getvalue()).decode()

    class Session:
        def call(self, operation, args=None):
            if operation == 'navigate':
                return {'target': '1:new-doc', 'account_key': 'same-account'}
            if operation == 'cards':
                raise RuntimeError('account_changed')
            if operation == 'open_profile':
                return {'opened': True}
            if args['action'] == 'prepare':
                return {'capture_id': 'test', 'text': ''}
            if args['action'] == 'release':
                return {'released': True}
            return {'top': 0, 'height': 100, 'total': 100, 'unstable': False, 'png': encoded}

    result = capture_extension(Session(), {'id': 'one', 'contact_status': 'unknown'}, tmp_path/'one')
    assert result['status'] == 'partial'
    assert result['reason'] == 'account_changed'
    assert (tmp_path/'one'/'segment-000.png').exists()


def test_cropped_diagnostic_is_saved_once_and_never_complete(tmp_path):
    import base64
    class Session:
        steps = 0
        def call(self, operation, args=None):
            if operation == 'open_profile':
                return {'opened': True}
            if operation == 'cards':
                return []
            if args['action'] == 'prepare':
                return {'capture_id': 'test', 'text': ''}
            if args['action'] == 'release':
                return {'released': True}
            self.steps += 1
            return {'top': 0, 'height': 100, 'total': 100, 'unstable': False, 'cropped': True,
                    'png': base64.b64encode(b'diagnostic-pixels').decode()}
    from boss_cli.precontact_capture import capture_extension
    session = Session()
    result = capture_extension(session, {'id':'one', 'contact_status':'unknown'}, tmp_path/'one', refresh=False)
    assert result['status'] == 'partial'
    assert result['reason'] == 'visible_viewport_diagnostic_only'
    assert session.steps == 1
    assert (tmp_path/'one'/'diagnostic-000.png').read_bytes() == b'diagnostic-pixels'


def test_layout_change_between_stable_segments_never_claims_complete(tmp_path):
    import base64

    from boss_cli.precontact_capture import capture_extension
    class Session:
        steps=0
        def call(self,operation,args=None):
            if operation=='open_profile':return {'opened':True}
            if operation=='cards':return []
            if args['action']=='prepare':return {'capture_id':'test','text':''}
            if args['action']=='release':return {'released':True}
            self.steps+=1
            return {'top':0 if self.steps==1 else 80,'height':100,'total':200 if self.steps==1 else 300,
                    'box':{'width':100},'unstable':False,'png':base64.b64encode(b'diagnostic').decode()}
    result=capture_extension(Session(),{'id':'one','contact_status':'unknown'},tmp_path/'one',max_segments=2,refresh=False)
    assert result['status']=='partial'
    assert result['reason']=='layout_changed_between_segments'
