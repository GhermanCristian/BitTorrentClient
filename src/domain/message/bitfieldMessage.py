from typing import Final
from domain.message.messageWithLengthAndID import MessageWithLengthAndID
from bitarray import bitarray


class BitfieldMessage(MessageWithLengthAndID):
    MESSAGE_ID: Final[int] = 5
    BASE_LENGTH_PREFIX: Final[int] = 1  # messageID = 1B;

    def __init__(self, bitfield: bitarray):
        super().__init__(self.BASE_LENGTH_PREFIX + len(bitfield), self.MESSAGE_ID)
        self.__bitfield: bytes = bitfield.tobytes()

    def getMessageContent(self) -> bytes:
        return super().getMessageContent() + self.__bitfield

    @property
    def bitfield(self) -> bytes:
        return self.__bitfield