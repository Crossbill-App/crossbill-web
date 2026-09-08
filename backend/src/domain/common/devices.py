"""Device identifiers Crossbill reserves for itself."""

# What a reading session made in the browser records as its device, so that
# browser reading is distinguishable from an e-reader's in the sessions list --
# and so that its content hash cannot collide with a KOReader session that
# happened to start at the same instant.
#
# It lives in ``domain/common`` because three unrelated places need the same
# string and none of them may reach into another's module: the web reader
# stamps it on the sessions it writes, the resume path leaves those sessions
# out of the search for where *another* device left off, and the KOReader sync
# refuses it, because a synced session wearing this name would be invisible to
# that search. ADR-0004 §6 keeps ``reading`` from depending on the web reader
# existing, so the name they share is not the web reader's to own.
WEB_READER_DEVICE_ID = "crossbill-web-reader"
