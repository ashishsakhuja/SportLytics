from app.services.team_aliases import resolve_team_alias


def test_resolve_team_alias_uses_sport_scope_for_shared_names() -> None:
    assert resolve_team_alias('giants', sport='nfl') == 'NYG'
    assert resolve_team_alias('giants', sport='mlb') == 'SF'
    assert resolve_team_alias('cardinals', sport='nfl') == 'ARI'
    assert resolve_team_alias('cardinals', sport='mlb') == 'STL'


def test_resolve_team_alias_handles_common_variants() -> None:
    assert resolve_team_alias('washington commanders', sport='nfl') == 'WAS'
    assert resolve_team_alias('la dodgers', sport='mlb') == 'LAD'
    assert resolve_team_alias('ny knicks', sport='nba') == 'NYK'
