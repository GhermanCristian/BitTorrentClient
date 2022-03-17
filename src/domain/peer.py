class Peer:
    def __init__(self, IP: int, port: int):
        self.__IP: int = IP
        self.__port: int = port
        self.__amChokingIt: bool = True
        self.__isChokingMe: bool = True
        self.__amInterestedInIt: bool = False
        self.__isInterestedInMe: bool = False

    @property
    def IP(self) -> int:
        return self.__IP

    @property
    def port(self) -> int:
        return self.__port

    @property
    def amChokingIt(self) -> bool:
        return self.__amChokingIt

    @property
    def isChokingMe(self) -> bool:
        return self.__isChokingMe

    @property
    def amInterestedInIt(self) -> bool:
        return self.__amInterestedInIt

    @property
    def isInterestedInMe(self) -> bool:
        return self.__isInterestedInMe

    def __str__(self) -> str:
        firstOctet = (self.__IP // 256 ** 3) % 256
        secondOctet = (self.__IP // 256 ** 2) % 256
        thirdOctet = (self.__IP // 256 ** 1) % 256
        fourthOctet = self.__IP % 256
        return f"""{firstOctet}.{secondOctet}.{thirdOctet}.{fourthOctet}:{self.__port};
            amChokingIt={self.__amChokingIt}; isChokingMe={self.__isChokingMe};
            amInterestedInIt={self.__amInterestedInIt}; isInterestedInMe={self.__isInterestedInMe};"""

    def __eq__(self, other):
        return isinstance(other, Peer) and self.__IP == other.IP and self.__port == other.port and self.__amChokingIt == other.amChokingIt \
               and self.__isChokingMe == other.isChokingMe and self.__amInterestedInIt == other.amInterestedInIt \
               and self.__isInterestedInMe == other.isInterestedInMe
