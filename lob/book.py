# lob/book.py

from collections import deque
import random
import time
import numpy as np


class Order:    # container for single order
    def __init__(self, order_id, side, price, size):

        self.id = order_id
        self.side = side      # "buy" or "sell"
        self.price = price
        self.size = size

class LimitOrderBook:
    def __init__(self):
        self.bids = {}   # price → queue of buy orders
        self.asks = {}   # price → queue of sell orders
        self.trades = [] # list of (price, size)
        self.order_index = {}   # order_id -> (side, price, order_object)

    def _best_bid(self):
        return max(self.bids.keys()) if self.bids else None  # Returns the highest bid price

    def _best_ask(self):
        return min(self.asks.keys()) if self.asks else None # returns min ask price

    def add_limit_order(self, order):
        """Add a limit order to the book or match it if marketable."""
        self.order_index[order.id] = (order.side, order.price, order)  #store index before match, then even partially filled can be cancelled
        if order.side == "buy":
            return self._match_buy(order)
        else:
            return self._match_sell(order)
    def _match_buy(self, order):
        while order.size > 0 and self.asks:
            best_ask = self._best_ask()  #Identify the best ask
            if order.price < best_ask:  #Check if the buy order is marketable
                break  # not marketable
#We loop while: The incoming order still has remaining size. There are asks in the book.
#Get the queue of sell orders at the best ask
            ask_queue = self.asks[best_ask]  # FIFO queue, first in first out
            best_order = ask_queue[0]   #oldest one , both of these enforce price-time priority

            trade_size = min(order.size, best_order.size)  #ensure we never overfill order
            order.size -= trade_size    #reduce both sizes
            best_order.size -= trade_size

            self.trades.append((best_ask, trade_size)) #Record the trade

            if best_order.size == 0: ##If the resting order is fully filled
                del self.order_index[best_order.id] 
                ask_queue.popleft() # Remove it from the queue. (popleft removes furthest left el)
                if not ask_queue:  #If the queue is empty, remove the entire price level.
                    del self.asks[best_ask]

        # If remaining size, add to book
        if order.size > 0:
            self.bids.setdefault(order.price, deque()).append(order) #setdefault ensures a queue exists at that price. Append adds order to end of queue.

    def _match_sell(self, order):
        while order.size > 0 and self.bids:
            best_bid = self._best_bid()
            if order.price > best_bid:
                break  # not marketable

            bid_queue = self.bids[best_bid]
            best_order = bid_queue[0]

            trade_size = min(order.size, best_order.size)
            order.size -= trade_size
            best_order.size -= trade_size

            self.trades.append((best_bid, trade_size))

            if best_order.size == 0:
                del self.order_index[best_order.id]
                bid_queue.popleft()
                if not bid_queue:
                    del self.bids[best_bid]

        # If remaining size, add to book
        if order.size > 0:
            self.asks.setdefault(order.price, deque()).append(order)

    def snapshot(self):

        return {"best_bid": self._best_bid(),"best_ask": self._best_ask(),"bids": {p: sum(o.size for o in q) for p, q in self.bids.items()},"asks": {p: sum(o.size for o in q) for p, q in self.asks.items()},"trades": self.trades[-5:]}

        
    def add_market_order(self, side, size):

        if side == "buy":
            return self._market_buy(size)
    
        # match best ask until size is gone
        else:
            return self._market_sell(size)

        # match until size is gone
    def _market_buy(self, size):
            """Market buy: hit best asks until size is gone or no asks remain."""
            while size > 0 and self.asks:
                best_ask = self._best_ask()
                ask_queue = self.asks[best_ask]
                best_order = ask_queue[0]

                trade_size = min(size, best_order.size)
                size -= trade_size
                best_order.size -= trade_size
        
                self.trades.append((best_ask, trade_size))
    
                if best_order.size == 0:
                    ask_queue.popleft()
                    if not ask_queue:
                        del self.asks[best_ask]
    
     
    def _market_sell(self,size):
        while size>0 and self.bids:
            best_bid= self._best_bid()
            bid_queue=self.bids[best_bid]
            best_order=bid_queue[0]

            trade_size = min(size, best_order.size)
            size -= trade_size
            best_order.size -= trade_size

            self.trades.append((best_bid, trade_size))


            if best_order.size ==0:
                bid_queue.popleft()
                if not bid_queue:
                    del self.bids[best_bid]
        


    def cancel_order(self, order_id):

        """Cancel an existing resting order by ID."""
        if order_id not in self.order_index:
            return print("order not found or already filled")

        side, price, order_obj = self.order_index[order_id]

        # Select correct book side
        book = self.bids if side == "buy" else self.asks

        if price not in book:
            return False   # price level disappeared (should not happen)

        queue = book[price]

        # Remove the order object from the queue
        for i, o in enumerate(queue):    #scan through queue and remove it
            if o.id == order_id:
                queue.remove(o)
                break

        # Clean up empty price level
        if not queue:
            del book[price]    #if price level empty, remove it 

        # Remove from index
        del self.order_index[order_id]

        return True


    #add mid,spread metricsfor random flow, very simple

    def mid_price(self):
        best_bid = self._best_bid() if self.bids else None
        best_ask = self._best_ask() if self.asks else None

        # If both sides exist → normal mid
        if best_bid is not None and best_ask is not None:
           mid = (best_bid + best_ask) / 2
           self.last_mid = mid
           return mid

    # If only one side exists → use that as mid
        if best_bid is not None:
            self.last_mid = best_bid
            return best_bid

        if best_ask is not None:
            self.last_mid = best_ask
            return best_ask

    # If book is empty → fallback to last mid or 100
        if hasattr(self, "last_mid") and self.last_mid is not None:
            return self.last_mid

        return 100



    def spread(self):
        if self.bids and self.asks:
            return self._best_ask() - self._best_bid()
        return None

    

