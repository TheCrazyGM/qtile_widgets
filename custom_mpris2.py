from libqtile.widget import Mpris2


class CustomMpris2(Mpris2):
    """
    A custom Mpris2 widget that dynamically hides the artist/title and
    separator when artist or title metadata is missing.
    """

    def get_track_info(self, metadata) -> str:
        # First, populate `self.metadata` just as the parent class does.
        super().get_track_info(metadata)

        # Now, apply the conditional formatting logic.
        format_string = self.format

        # Check if the artist or title field is missing or empty.
        has_artist = self.metadata.get("xesam:artist")
        has_title = self.metadata.get("xesam:title")

        if not has_artist and has_title:
            format_string = "{xesam:title}"
        elif not has_title and has_artist:
            format_string = "{xesam:artist}"

        # Format the string using the selected format.
        track = self._formatter.format(format_string, **self.metadata)
        return track.replace("\n", "")
