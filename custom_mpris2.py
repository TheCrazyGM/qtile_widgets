from libqtile.widget import Mpris2


class CustomMpris2(Mpris2):
    """
    A custom Mpris2 widget that dynamically hides the artist/title and
    separator when artist or title metadata is missing.
    """

    def get_track_info(self, metadata) -> str:
        # First, populate `self.metadata` just as the parent class does.
        self.metadata = {}
        for key, value in metadata.items():
            val = getattr(value, "value", None)
            if isinstance(val, str):
                self.metadata[key] = val
            elif isinstance(val, list):
                self.metadata[key] = self.separator.join(
                    str(y) for y in val if isinstance(y, str)
                )

        if self.player is not None:
            self.metadata["qtile:player"] = self.player

        # Now, apply the conditional formatting logic.
        format_string = self.format

        # Check if the artist field is missing or empty.
        if not self.metadata.get("xesam:artist"):
            format_string = "{xesam:title}"

        # Check if the title field is missing or empty.
        if not self.metadata.get("xesam:title"):
            format_string = "{xesam:artist}"
        # Format the string using the selected format.
        track = self._formatter.format(format_string, **self.metadata)
        return track.replace("\n", "")
