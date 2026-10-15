"""Optional browser assertions for the shared visualizer (no Playwright import).

A consumer supplies a live synchronous Playwright Page. This checks rendering,
not a second sampler. Call while paused after independently checking the native
samples against the authoritative recording/catalogue.
"""
from __future__ import annotations


def check_display_modes(page) -> dict:
    state = page.evaluate('window.audition.state()')
    assert not state['running'], 'Run display assertions on a paused transport'
    review = page.evaluate('window.audition.review()')
    before = page.evaluate('window.audition.state().beat')
    page.locator('#view-mode').select_option('bars')
    page.wait_for_function('window.audition.state().viewMode === "bars"')
    cards = page.locator('#compare-grid .card')
    if cards.count() == 0:
        cards = page.locator('#grid .card')
    checked = 0
    for index in range(min(4, cards.count())):
        card = cards.nth(index)
        card.scroll_into_view_if_needed()
        card.locator('.dimension-bar').first.wait_for()
        page.wait_for_timeout(60)
        result = card.evaluate('''c => {
          const i=c.motionPlot.i, p=window.audition.metadata()[i];
          const pip=Math.floor(window.audition.state().beat*64+1e-8);
          const expected=window.audition.sample(i,pip);
          const bars=[...c.querySelectorAll('.dimension-bar')];
          const amplitude=Number(document.getElementById('amplitude').value)/100;
          return {dimensions:expected.length, bars:bars.length,
            values:bars.every((b,j)=>Number(b.dataset.value)===expected[j]),
            geometry:bars.every((b,j)=>{
              const value=Math.max(-1,Math.min(1,expected[j]*amplitude));
              const f=b.querySelector('.bar-fill');
              return Math.abs(parseFloat(f.style.height)-Math.abs(value)*50)<1e-4 &&
                Math.abs(parseFloat(f.style.top)-(value>=0?50-value*50:50))<1e-4;
            }),
            hidden:c.querySelector('.stage').hidden && c.querySelector('.wave').hidden,
            labels:bars.map(b=>b.querySelector('[role=meter]').getAttribute('aria-label')),
            expectedLabels:p.dimensions || ['X','Y','Z']};
        }''')
        assert result['bars'] == result['dimensions'], result
        assert result['values'] and result['geometry'] and result['hidden'], result
        assert result['labels'] == result['expectedLabels'], result
        checked += result['dimensions']
    assert checked > 0, 'No bar channels were rendered'
    assert page.evaluate('window.audition.review()') == review
    assert abs(page.evaluate('window.audition.state().beat') - before) < 1e-6
    assert not page.evaluate('window.audition.state().running')
    page.locator('#view-mode').select_option('xy')
    page.wait_for_function('window.audition.state().viewMode === "xy"')
    assert not page.locator('#trails').is_disabled()
    assert cards.first.locator('.channel-bars').is_hidden()
    assert page.evaluate('window.audition.review()') == review
    return {'view_modes': ['xy', 'bars'], 'all_dimension_bars': True,
            'bar_values_match_native': True, 'bar_geometry_matches_scale': True,
            'bar_channels_checked': checked, 'mode_switch_preserves_time_and_reviews': True}


def check_running_view_switch(page) -> None:
    """Changing only presentation must not pause or restart the shared clock."""
    assert page.evaluate('window.audition.state().running')
    beat = page.evaluate('window.audition.state().beat')
    page.locator('#view-mode').select_option('bars')
    assert page.evaluate('window.audition.state().running')
    assert page.evaluate('window.audition.state().beat') >= beat
    page.locator('#view-mode').select_option('xy')
    assert page.evaluate('window.audition.state().running')
