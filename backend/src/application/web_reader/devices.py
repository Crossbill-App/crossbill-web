"""How a reading session made in the browser names the device that wrote it."""

# What a session created by the web reader records as its device, so that
# browser reading is distinguishable from an e-reader's in the sessions list --
# and so that its content hash cannot collide with a KOReader session that
# happened to start at the same instant.
#
# It lives on its own because both directions need it: the write path stamps it
# on the sessions it creates, and the resume path uses it to leave those same
# sessions out of the search for where another device left off.
WEB_READER_DEVICE_ID = "crossbill-web-reader"
