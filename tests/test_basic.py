def test_import_modules():
    from carim_discord_bot import main
    print(main.format_help(include_admin=True))
