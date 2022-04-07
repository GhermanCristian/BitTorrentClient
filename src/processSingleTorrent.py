import asyncio
from asyncio import StreamReader
from typing import List, Final
from bitarray import bitarray
import utils
from domain.message.handshakeMessage import HandshakeMessage
from domain.message.interestedMessage import InterestedMessage
from domain.message.messageWithLengthAndID import MessageWithLengthAndID
from domain.message.requestMessage import RequestMessage
from domain.peer import Peer
from domain.validator.handshakeResponseValidator import HandshakeResponseValidator
from messageProcessor import MessageProcessor
from messageWithLengthAndIDFactory import MessageWithLengthAndIDFactory
from torrentMetaInfoScanner import TorrentMetaInfoScanner
from trackerConnection import TrackerConnection


class ProcessSingleTorrent:
    ATTEMPTS_TO_CONNECT_TO_PEER: Final[int] = 3
    MESSAGE_ID_LENGTH: Final[int] = 1

    def __init__(self, torrentFileName: str):
        self.__scanner: TorrentMetaInfoScanner = TorrentMetaInfoScanner(torrentFileName)
        trackerConnection: TrackerConnection = TrackerConnection()
        trackerConnection.makeTrackerRequest(self.__scanner.getAnnounceURL(), self.__scanner.getInfoHash(), self.__scanner.getTotalContentSize())
        self.__completedPieces: bitarray = bitarray(self.__scanner.getPieceCount())  # this will have to be loaded from disk when resuming downloads
        self.__completedPieces.setall(0)
        self.__peerList: List[Peer] = trackerConnection.peerList
        self.__host: Final[Peer] = trackerConnection.host
        self.__infoHash: bytes = self.__scanner.getInfoHash()
        self.__peerID: str = TrackerConnection.PEER_ID
        self.__handshakeMessage: HandshakeMessage = HandshakeMessage(self.__infoHash, self.__peerID)
        self.__handshakeResponseValidator: HandshakeResponseValidator = HandshakeResponseValidator(self.__infoHash, HandshakeMessage.CURRENT_PROTOCOL)

    """
    Attempts to read byteCount bytes. If too many empty messages are read in a row, the reading is aborted
    @:param reader - where the data is read from
    @:param byteCount - the number of bytes to be read
    @:returns The read data, of length byteCount or less
    """
    @staticmethod
    async def __attemptToReadBytes(reader: StreamReader, byteCount: int) -> bytes:
        payload: bytes = b""
        completedLength: int = 0
        consecutiveEmptyMessages: int = 0
        while completedLength < byteCount and consecutiveEmptyMessages < 3:
            newSequence: bytes = await reader.read(byteCount - completedLength)  # throws exception ?
            payload += newSequence
            completedLength += len(newSequence)
            if len(newSequence) == 0:
                consecutiveEmptyMessages += 1
            else:
                consecutiveEmptyMessages = 0
        return payload

    """
    Attempts to connect to another peer
    @:param otherPeer - the peer we are trying to communicate with
    @:returns True, if the connection was successful, false otherwise
    """
    async def __attemptToConnectToPeer(self, otherPeer: Peer) -> bool:
        for attempt in range(self.ATTEMPTS_TO_CONNECT_TO_PEER):
            try:
                otherPeer.streamReader, otherPeer.streamWriter = await asyncio.open_connection(otherPeer.getIPRepresentedAsString(), otherPeer.port)
                await self.__handshakeMessage.send(otherPeer)
                handshakeResponse: bytes = await self.__attemptToReadBytes(otherPeer.streamReader, HandshakeMessage.HANDSHAKE_LENGTH)
                if self.__handshakeResponseValidator.validateHandshakeResponse(handshakeResponse):
                    return True
                await otherPeer.closeConnection()
            except Exception:
                await otherPeer.closeConnection()
        return False

    async def __closeAllConnections(self) -> None:
        await asyncio.gather(*[
            peer.closeConnection() for peer in self.__peerList if peer.hasActiveConnection()
        ])

    @staticmethod
    async def __sendRequestMessage(otherPeer: Peer, pieceIndex: int, beginOffset: int, blockLength: int) -> None:
        await RequestMessage(pieceIndex, beginOffset, blockLength).send(otherPeer)

    async def __requestPiece(self, otherPeer: Peer) -> None:
        pieceIndex: int = 69
        if not otherPeer.isChokingMe and otherPeer.amInterestedInIt and otherPeer.availablePieces[pieceIndex]:
            print(f"making request to {otherPeer.getIPRepresentedAsString()}")
            await self.__sendRequestMessage(otherPeer, pieceIndex, 0, 2 ** 14)

    """
    Reads an entire message from another peer
    @:param otherPeer - the peer we receive the message from
    @:returns True, if the message has been read successfully, false otherwise
    """
    async def __readMessage(self, otherPeer: Peer) -> bool:
        try:
            lengthPrefix: bytes = await self.__attemptToReadBytes(otherPeer.streamReader, 4)
        except ConnectionError as e:
            print(e)
            return False

        if len(lengthPrefix) == 0:
            print(f"nothing was read - {otherPeer.getIPRepresentedAsString()}")
            return True
        if lengthPrefix == utils.convertIntegerTo4ByteBigEndian(0):
            print(f"keep alive message - {otherPeer.getIPRepresentedAsString()}")
            return True

        messageID: bytes = await self.__attemptToReadBytes(otherPeer.streamReader, self.MESSAGE_ID_LENGTH)
        payloadLength: int = utils.convert4ByteBigEndianToInteger(lengthPrefix) - self.MESSAGE_ID_LENGTH
        payload: bytes = await self.__attemptToReadBytes(otherPeer.streamReader, payloadLength)

        if messageID == utils.convertIntegerTo1Byte(20):
            print(f"Extended protocol - ignored for now - {otherPeer.getIPRepresentedAsString()}")
            return True

        try:
            message: MessageWithLengthAndID = MessageWithLengthAndIDFactory.getMessageFromIDAndPayload(messageID, payload)
            MessageProcessor(otherPeer).processMessage(message)
            print(f"{message} - {otherPeer.getIPRepresentedAsString()}")
        except Exception as e:
            print(e)

        return True

    async def __startPeer(self, otherPeer) -> None:
        if not await self.__attemptToConnectToPeer(otherPeer):
            return

        await InterestedMessage().send(otherPeer)
        otherPeer.amInterestedInIt = True
        for _ in range(6):  # will probably become while True
            if not otherPeer.hasActiveConnection() or not await self.__readMessage(otherPeer):
                return
            await self.__requestPiece(otherPeer)

    async def __peerCommunication(self) -> None:
        try:
            self.__peerList.remove(self.__host)
        except ValueError:
            pass

        await asyncio.gather(*[
            self.__startPeer(otherPeer)
            for otherPeer in self.__peerList
        ])

    """
    Wrapper for the method which communicates with the peers
    """
    def start(self) -> None:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # due to issues with closing the event loop in windows
        asyncio.run(self.__peerCommunication())
