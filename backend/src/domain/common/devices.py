"""Device identifiers Crossbill reserves for itself."""

# What a reading session made in the browser records as its device, so browser
# reading is distinguishable from an e-reader's -- and so its content hash cannot
# collide with a KOReader session that began at the same instant.
#
# In ``domain/common`` because the modules that need the same string may not reach
# into each other: the web reader stamps it, and the resume path leaves the
# sessions wearing it out of the search for where *another* device left off.
WEB_READER_DEVICE_ID = "crossbill-web-reader"
